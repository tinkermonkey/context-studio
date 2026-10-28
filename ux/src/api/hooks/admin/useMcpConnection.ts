import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { adminService } from "@/api/services/admin";

/** The MCP endpoint URL and bearer token, for registering an MCP client. */
export function useMcpConnection() {
  return useQuery({
    queryKey: QUERY_KEYS.mcpConnection,
    queryFn: () => adminService.getMcpConnection(),
  });
}
