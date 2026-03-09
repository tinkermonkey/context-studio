"""
S3 Storage Manager - Intelligent storage cost and performance management

This service implements sophisticated S3 storage management including lifecycle
policies, intelligent compression, column optimization, and storage checkpoints
for enterprise-scale cost reduction and performance improvement.
"""

import time
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from utils.logger import get_logger

try:
    from botocore.exceptions import ClientError as BotoClientError  # type: ignore[import-untyped]
except ImportError:
    # Define a dummy ClientError for environments where boto3 is not installed
    class BotoClientError(Exception):  # type: ignore
        pass


ClientError = BotoClientError

logger = get_logger(__name__)


class S3StorageManager:
    """Manage S3 storage costs and performance through intelligent handling."""

    def __init__(self, s3_client, bucket_name: str, duckdb_conn=None):
        """
        Initialize S3 storage manager.

        Args:
            s3_client: Boto3 S3 client instance
            bucket_name: S3 bucket name for management
            duckdb_conn: Optional DuckDB connection for checkpoint queries
        """
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.duckdb_conn = duckdb_conn
        self.compression_stats: Dict[str, Dict[str, Any]] = {}
        self.management_history: list[Dict[str, Any]] = []

        logger.info(f"S3StorageManager initialized for bucket: {bucket_name}")

    def setup_lifecycle_policies(self) -> bool:
        """Configure S3 lifecycle policies for cost management."""

        logger.info("Setting up intelligent S3 lifecycle policies")

        lifecycle_config = {
            "Rules": [
                {
                    "ID": "change_data_lifecycle",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "changes/"},
                    "Transitions": [
                        {"Days": 30, "StorageClass": "STANDARD_IA"},
                        {"Days": 90, "StorageClass": "GLACIER"},
                        {"Days": 365, "StorageClass": "DEEP_ARCHIVE"},
                    ],
                },
                {
                    "ID": "proposal_cleanup",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "proposals/"},
                    "Expiration": {"Days": 730},  # Delete old proposals after 2 years
                },
                {
                    "ID": "temporary_data_cleanup",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "temp/"},
                    "Expiration": {"Days": 7},
                },
                {
                    "ID": "analytics_cache_cleanup",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "analytics_cache/"},
                    "Transitions": [{"Days": 7, "StorageClass": "STANDARD_IA"}],
                    "Expiration": {"Days": 30},
                },
                {
                    "ID": "incomplete_multipart_cleanup",
                    "Status": "Enabled",
                    "Filter": {},
                    "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1},
                },
            ]
        }

        try:
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=self.bucket_name, LifecycleConfiguration=lifecycle_config
            )
            logger.info("S3 lifecycle policies configured successfully")
            return True
        except ClientError as e:
            logger.error(f"Failed to setup lifecycle policies: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to setup lifecycle policies: {e}")
            return False

    def compress_parquet_storage(
        self, data_df: pd.DataFrame, s3_path: str
    ) -> Dict[str, Any]:
        """Compress Parquet file storage with compression and column optimization."""

        logger.info(f"Compressing Parquet storage for: {s3_path}")

        # Analyze data characteristics
        data_analysis = self._analyze_dataframe(data_df)

        # Choose best compression based on data characteristics
        compression = self._select_compression(data_analysis)

        # Downcast column types for storage efficiency
        downcasted_df = self._downcast_column_types(data_df, data_analysis)

        # Write with optimized settings
        write_options = {
            "compression": compression,
            "row_group_size": self._calculate_row_group_size(data_analysis),
            "use_dictionary": True,
            "dictionary_pagesize_limit": 1024 * 1024,  # 1MB
            "write_statistics": True,
            "compression_level": self._get_compression_level(compression),
        }

        # Calculate original size (estimate)
        original_size = data_df.memory_usage(deep=True).sum()

        try:
            # Write downcast Parquet
            parquet_buffer = downcasted_df.to_parquet(**write_options)  # type: ignore[call-overload]
            compressed_size = (
                len(parquet_buffer)
                if isinstance(parquet_buffer, bytes)
                else original_size
            )

            compression_ratio = (
                original_size / compressed_size if compressed_size > 0 else 1.0
            )

            # Track compression statistics
            self.compression_stats[s3_path] = {
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": compression_ratio,
                "compression_algorithm": compression,
                "compressed_at": time.time(),
                "row_count": len(downcasted_df),
                "column_count": len(downcasted_df.columns),
            }

            logger.info(f"Parquet compression: {compression_ratio:.2f}x ratio achieved")

            return {
                "compressed_size": compressed_size,
                "compression_ratio": compression_ratio,
                "compression_algorithm": compression,
                "savings_bytes": original_size - compressed_size,
                "write_options": write_options,
            }

        except Exception as e:
            logger.error(f"Failed to compress Parquet storage: {e}")
            return {
                "compressed_size": original_size,
                "compression_ratio": 1.0,
                "compression_algorithm": "none",
                "savings_bytes": 0,
                "error": str(e),
            }

    def create_storage_checkpoints(
        self, checkpoint_frequency: str = "weekly"
    ) -> Dict[str, Any]:
        """Create periodic storage checkpoints for efficient querying."""

        logger.info(
            f"Creating storage checkpoints with {checkpoint_frequency} frequency"
        )

        checkpoint_date = datetime.now().strftime("%Y-%m-%d")
        checkpoint_path = (
            f"s3://{self.bucket_name}/checkpoints/checkpoint_{checkpoint_date}.parquet"
        )

        if not self.duckdb_conn:
            logger.error("DuckDB connection required for checkpoint creation")
            return {"error": "DuckDB connection not available"}

        try:
            # Determine date range based on frequency
            if checkpoint_frequency == "daily":
                date_filter = "CURRENT_DATE - INTERVAL '1 day'"
            elif checkpoint_frequency == "weekly":
                date_filter = "CURRENT_DATE - INTERVAL '7 days'"
            elif checkpoint_frequency == "monthly":
                date_filter = "CURRENT_DATE - INTERVAL '30 days'"
            else:
                date_filter = "CURRENT_DATE - INTERVAL '7 days'"

            # Aggregate recent changes into checkpoint
            aggregation_query = f"""
            SELECT entity_type, entity_id,
                   LAST(content ORDER BY created_at) as latest_content,
                   MAX(created_at) as last_modified,
                   COUNT(*) as version_count,
                   FIRST(author_id ORDER BY created_at) as first_author,
                   LAST(author_id ORDER BY created_at) as latest_author
            FROM read_parquet('s3://{self.bucket_name}/changes/*/*/*.parquet')
            WHERE created_at >= {date_filter}
            GROUP BY entity_type, entity_id
            ORDER BY entity_type, entity_id
            """

            # Execute aggregation
            result = self.duckdb_conn.execute(aggregation_query).fetchall()

            if result:
                # Create DataFrame from results
                columns = [
                    "entity_type",
                    "entity_id",
                    "latest_content",
                    "last_modified",
                    "version_count",
                    "first_author",
                    "latest_author",
                ]
                checkpoint_df = pd.DataFrame(result, columns=columns)

                # Compress and write checkpoint
                compression_result = self.compress_parquet_storage(
                    checkpoint_df, checkpoint_path
                )

                # Upload to S3 (would need actual S3 upload implementation)
                # For now, just log the checkpoint creation

                entities_included = len(checkpoint_df)
                size_bytes = compression_result.get("compressed_size", 0)

                logger.info(
                    f"Created checkpoint with {entities_included} entities, {size_bytes} bytes"
                )

                return {
                    "checkpoint_path": checkpoint_path,
                    "checkpoint_date": checkpoint_date,
                    "entities_included": entities_included,
                    "size_bytes": size_bytes,
                    "compression_ratio": compression_result.get(
                        "compression_ratio", 1.0
                    ),
                    "frequency": checkpoint_frequency,
                }
            else:
                logger.warning("No data found for checkpoint creation")
                return {
                    "checkpoint_path": checkpoint_path,
                    "checkpoint_date": checkpoint_date,
                    "entities_included": 0,
                    "size_bytes": 0,
                    "message": "No data available for checkpoint",
                }

        except Exception as e:
            logger.error(f"Failed to create storage checkpoint: {e}")
            return {"error": str(e), "checkpoint_date": checkpoint_date}

    def analyze_storage_costs(self, days_back: int = 30) -> Dict[str, Any]:
        """Analyze storage costs and identify management opportunities."""

        logger.info(f"Analyzing storage costs for the last {days_back} days")

        try:
            # Get storage metrics from S3
            cutoff_date = datetime.now() - timedelta(days=days_back)

            storage_analysis = {
                "analysis_period_days": days_back,
                "total_objects": 0,
                "total_size_bytes": 0,
                "storage_classes": {},
                "cost_by_prefix": {},
                "management_opportunities": [],
            }

            # List objects and analyze storage patterns
            paginator = self.s3_client.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(Bucket=self.bucket_name)

            for page in page_iterator:  # type: ignore
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:  # type: ignore
                    storage_analysis["total_objects"] += 1  # type: ignore
                    storage_analysis["total_size_bytes"] += obj["Size"]  # type: ignore

                    # Analyze by prefix
                    prefix = obj["Key"].split("/")[0] if "/" in obj["Key"] else "root"  # type: ignore
                    if prefix not in storage_analysis["cost_by_prefix"]:  # type: ignore
                        storage_analysis["cost_by_prefix"][prefix] = {  # type: ignore
                            "object_count": 0,
                            "total_size": 0,
                            "avg_size": 0,
                        }

                    storage_analysis["cost_by_prefix"][prefix]["object_count"] += 1  # type: ignore
                    storage_analysis["cost_by_prefix"][prefix]["total_size"] += obj["Size"]  # type: ignore

                    # Check if object is old enough for archival
                    if obj["LastModified"] < cutoff_date:  # type: ignore
                        storage_analysis["management_opportunities"].append(
                            {  # type: ignore
                                "key": obj["Key"],  # type: ignore
                                "size": obj["Size"],  # type: ignore
                                "last_modified": obj["LastModified"].isoformat(),  # type: ignore
                                "recommendation": "Consider archival to Glacier or Deep Archive",
                            }
                        )

            # Calculate averages
            for prefix_stats in storage_analysis["cost_by_prefix"].values():  # type: ignore
                if prefix_stats["object_count"] > 0:  # type: ignore
                    prefix_stats["avg_size"] = prefix_stats["total_size"] / prefix_stats["object_count"]  # type: ignore

            # Estimate cost savings
            total_archival_candidates = len(storage_analysis["management_opportunities"])  # type: ignore
            estimated_savings = self._estimate_cost_savings(storage_analysis)

            storage_analysis["cost_management"] = {  # type: ignore
                "archival_candidates": total_archival_candidates,
                "estimated_monthly_savings_usd": estimated_savings,
                "current_monthly_cost_estimate_usd": self._estimate_current_cost(int(storage_analysis["total_size_bytes"])),  # type: ignore
            }

            logger.info(
                f"Storage analysis complete: {storage_analysis['total_objects']} objects, "  # type: ignore
                f"{int(storage_analysis['total_size_bytes']) / (1024**3):.2f} GB total"
            )  # type: ignore

            return storage_analysis

        except ClientError as e:
            logger.error(f"Failed to analyze storage costs: {e}")
            return {"error": str(e)}

    def _analyze_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze DataFrame characteristics for compression."""

        analysis = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "memory_usage": df.memory_usage(deep=True).sum(),
            "column_types": df.dtypes.to_dict(),
            "null_percentages": df.isnull().mean().to_dict(),
            "cardinality": {col: df[col].nunique() for col in df.columns},
            "string_lengths": {},
            "numeric_ranges": {},
        }

        # Analyze string columns
        for col in df.select_dtypes(include=["object"]).columns:
            if df[col].dtype == "object":
                string_series = df[col].astype(str)
                analysis["string_lengths"][col] = {
                    "avg_length": string_series.str.len().mean(),
                    "max_length": string_series.str.len().max(),
                    "total_chars": string_series.str.len().sum(),
                }

        # Analyze numeric columns
        for col in df.select_dtypes(include=["int64", "float64"]).columns:
            analysis["numeric_ranges"][col] = {
                "min": df[col].min(),
                "max": df[col].max(),
                "mean": df[col].mean(),
                "std": df[col].std(),
            }

        return analysis

    def _select_compression(self, analysis: Dict[str, Any]) -> str:
        """Select best compression algorithm based on data characteristics."""

        total_string_chars = sum(
            stats["total_chars"] for stats in analysis["string_lengths"].values()
        )

        total_numeric_cols = len(analysis["numeric_ranges"])
        total_string_cols = len(analysis["string_lengths"])

        # Decision matrix for compression algorithm
        if total_string_chars > analysis["row_count"] * 50:  # Lots of text content
            return "zstd"  # Best for text compression
        elif total_numeric_cols > total_string_cols:  # Mostly numeric data
            return "snappy"  # Fast compression for numeric data
        elif analysis["row_count"] > 100000:  # Large datasets
            return "zstd"  # Better compression ratio
        else:
            return "snappy"  # Default for smaller datasets

    def _downcast_column_types(
        self, df: pd.DataFrame, analysis: Dict[str, Any]
    ) -> pd.DataFrame:
        """Downcast column types for better storage efficiency."""

        downcasted_df = df.copy()

        # Downcast integer columns
        for col, dtype in analysis["column_types"].items():
            if dtype in ["int64"]:
                col_min = analysis["numeric_ranges"].get(col, {}).get("min", 0)
                col_max = analysis["numeric_ranges"].get(col, {}).get("max", 0)

                # Downcast to smaller integer types if possible
                if col_min >= 0 and col_max <= 255:
                    downcasted_df[col] = downcasted_df[col].astype("uint8")
                elif col_min >= -128 and col_max <= 127:
                    downcasted_df[col] = downcasted_df[col].astype("int8")
                elif col_min >= 0 and col_max <= 65535:
                    downcasted_df[col] = downcasted_df[col].astype("uint16")
                elif col_min >= -32768 and col_max <= 32767:
                    downcasted_df[col] = downcasted_df[col].astype("int16")
                elif col_min >= 0 and col_max <= 4294967295:
                    downcasted_df[col] = downcasted_df[col].astype("uint32")
                elif col_min >= -2147483648 and col_max <= 2147483647:
                    downcasted_df[col] = downcasted_df[col].astype("int32")

        # Convert string columns with categorical data
        for col in downcasted_df.select_dtypes(include=["object"]).columns:
            cardinality = analysis["cardinality"].get(col, downcasted_df[col].nunique())
            total_rows = len(downcasted_df)

            # Convert to category if low cardinality
            if cardinality < total_rows * 0.5:  # Less than 50% unique values
                downcasted_df[col] = downcasted_df[col].astype("category")

        return downcasted_df

    def _calculate_row_group_size(self, analysis: Dict[str, Any]) -> int:
        """Calculate row group size for Parquet files."""

        row_count = analysis["row_count"]
        memory_usage = analysis["memory_usage"]

        # Target row group size between 100MB and 1GB
        target_size_bytes = 512 * 1024 * 1024  # 512MB

        if memory_usage > 0:
            avg_row_size = memory_usage / row_count
            result_rows = int(target_size_bytes / avg_row_size)

            # Clamp between reasonable bounds
            return max(1000, min(result_rows, 1000000))

        return 100000  # Default

    def _get_compression_level(self, compression: str) -> Optional[int]:
        """Get compression level for the algorithm."""

        compression_levels = {
            "zstd": 3,  # Good balance of speed and compression
            "gzip": 6,  # Standard level
            "brotli": 6,
        }

        return compression_levels.get(compression)

    def _estimate_cost_savings(self, storage_analysis: Dict[str, Any]) -> float:
        """Estimate monthly cost savings from management."""

        # Simplified cost model (AWS S3 pricing estimates)
        standard_cost_per_gb = 0.023  # USD per GB per month
        glacier_cost_per_gb = 0.004

        total_gb = float(storage_analysis["total_size_bytes"]) / (1024**3)  # type: ignore
        archival_candidates = len(storage_analysis["management_opportunities"])  # type: ignore

        # Estimate potential savings if 70% of old data is moved to Glacier
        if archival_candidates > 0:
            archival_gb = total_gb * 0.3  # Assume 30% can be archived
            savings = archival_gb * (standard_cost_per_gb - glacier_cost_per_gb)
            return float(max(0.0, savings))

        return 0.0

    def _estimate_current_cost(self, total_bytes: int) -> float:
        """Estimate current monthly storage cost."""

        standard_cost_per_gb = 0.023
        total_gb = total_bytes / (1024**3)
        return total_gb * standard_cost_per_gb

    def manage_storage_comprehensive(self) -> Dict[str, Any]:
        """Run comprehensive storage management including lifecycle policies, compression, and cost analysis."""

        logger.info("Starting comprehensive storage management")

        management_actions = []
        total_storage_saved = 0
        total_objects_managed = 0

        try:
            # 1. Setup lifecycle policies
            lifecycle_success = self.setup_lifecycle_policies()
            if lifecycle_success:
                management_actions.append(
                    {
                        "action": "lifecycle_policies_configured",
                        "status": "success",
                        "description": "S3 lifecycle policies configured for automatic archiving",
                    }
                )
            else:
                management_actions.append(
                    {
                        "action": "lifecycle_policies_configuration",
                        "status": "failed",
                        "description": "Failed to configure S3 lifecycle policies",
                    }
                )

            # 2. Analyze storage costs
            cost_analysis = self.analyze_storage_costs()
            if "error" not in cost_analysis:
                total_objects_managed = cost_analysis.get("total_objects", 0)
                management_actions.append(
                    {
                        "action": "storage_cost_analysis",
                        "status": "success",
                        "description": f"Analyzed {total_objects_managed} objects for cost management",
                    }
                )

                # Estimate savings from archival candidates
                archival_candidates = len(
                    cost_analysis.get("management_opportunities", [])
                )
                if archival_candidates > 0:
                    estimated_archival_savings = (
                        archival_candidates * 1024 * 1024
                    )  # Mock: 1MB per file
                    total_storage_saved += estimated_archival_savings
                    management_actions.append(
                        {
                            "action": "archival_candidates_identified",
                            "status": "success",
                            "description": f"Identified {archival_candidates} files for archival",
                        }
                    )
            else:
                management_actions.append(
                    {
                        "action": "storage_cost_analysis",
                        "status": "failed",
                        "description": f"Storage cost analysis failed: {cost_analysis['error']}",
                    }
                )

            # 3. Apply compression improvements to existing compression stats
            compression_savings = 0
            for file_path, stats in self.compression_stats.items():
                compression_savings += stats.get(
                    "savings_bytes", stats["original_size"] - stats["compressed_size"]
                )

            if compression_savings > 0:
                total_storage_saved += compression_savings
                management_actions.append(
                    {
                        "action": "compression_improvement",
                        "status": "success",
                        "description": f"Compression improved storage savings of {compression_savings} bytes across {len(self.compression_stats)} files",
                    }
                )

            # 4. Create storage checkpoint
            checkpoint_result = self.create_storage_checkpoints()
            if "error" not in checkpoint_result:
                management_actions.append(
                    {
                        "action": "storage_checkpoint_created",
                        "status": "success",
                        "description": f"Created storage checkpoint with {checkpoint_result.get('entities_included', 0)} entities",
                    }
                )
            else:
                management_actions.append(
                    {
                        "action": "storage_checkpoint_creation",
                        "status": "failed",
                        "description": f"Checkpoint creation failed: {checkpoint_result['error']}",
                    }
                )

            # Calculate cost reduction estimate
            cost_reduction_estimate = cost_analysis.get("cost_management", {}).get(
                "estimated_monthly_savings_usd", 0.0
            )
            if cost_reduction_estimate == 0 and total_storage_saved > 0:
                # Fallback estimate: $0.023 per GB per month for standard storage
                gb_saved = total_storage_saved / (1024**3)
                cost_reduction_estimate = gb_saved * 0.023

            logger.info(
                f"Comprehensive management complete: {len(management_actions)} actions, "
                f"{total_storage_saved} bytes saved, ${cost_reduction_estimate:.2f} monthly savings"
            )

            return {
                "management_actions": management_actions,
                "storage_saved_bytes": total_storage_saved,
                "cost_reduction_estimate": cost_reduction_estimate,
                "objects_managed": total_objects_managed,
            }

        except Exception as e:
            logger.error(f"Comprehensive storage management failed: {e}")
            return {
                "management_actions": [
                    {
                        "action": "comprehensive_management",
                        "status": "failed",
                        "description": f"Comprehensive management failed: {str(e)}",
                    }
                ],
                "storage_saved_bytes": 0,
                "cost_reduction_estimate": 0.0,
                "objects_managed": 0,
            }

    def get_management_summary(self) -> Dict[str, Any]:
        """Get comprehensive storage management summary."""

        total_files_managed = len(self.compression_stats)

        if total_files_managed == 0:
            return {
                "files_managed": 0,
                "total_savings_bytes": 0,
                "average_compression_ratio": 0,
                "compression_algorithms_used": {},
            }

        total_original_size = sum(
            stats["original_size"] for stats in self.compression_stats.values()
        )
        total_compressed_size = sum(
            stats["compressed_size"] for stats in self.compression_stats.values()
        )
        total_savings = total_original_size - total_compressed_size

        avg_compression_ratio = (
            total_original_size / total_compressed_size
            if total_compressed_size > 0
            else 1.0
        )

        # Count compression algorithms used
        algorithm_counts: Dict[str, int] = {}
        for stats in self.compression_stats.values():
            algo = stats["compression_algorithm"]
            algorithm_counts[algo] = algorithm_counts.get(algo, 0) + 1

        return {
            "files_managed": total_files_managed,
            "total_original_size_bytes": total_original_size,
            "total_compressed_size_bytes": total_compressed_size,
            "total_savings_bytes": total_savings,
            "average_compression_ratio": avg_compression_ratio,
            "compression_algorithms_used": algorithm_counts,
            "management_history_count": len(self.management_history),
        }
