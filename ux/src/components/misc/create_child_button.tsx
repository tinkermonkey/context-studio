import React from "react";
import { Button } from "flowbite-react";
import { Plus } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import type { StructureNode } from "@/api/types/structureNodes";
import { CreateChildModal } from "./create_child_modal";
import { DomainForm } from "@/components/forms/domain_form";
import { TermForm } from "@/components/forms/term_form";

interface CreateChildButtonProps {
  parentType: "layer" | "domain" | "term";
  parentId: string;
  parentObject: StructureNode;
  childType: "domain" | "term";
  onSuccess?: (child: any) => void;
  className?: string;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
}

export const CreateChildButton: React.FC<CreateChildButtonProps> = ({
  parentType,
  parentId,
  parentObject,
  childType,
  onSuccess,
  className,
  size = "xs",
}) => {
  const [isModalOpen, setIsModalOpen] = React.useState(false);
  const queryClient = useQueryClient();

  // Invalidate related queries after child creation
  const invalidateRelatedQueries = (
    parentType: string,
    parentId: string,
    childType: string,
  ) => {
    queryClient.invalidateQueries({
      queryKey: [parentType, parentId],
    });
    queryClient.invalidateQueries({
      queryKey: [childType],
    });

    // Invalidate specific list queries
    if (childType === "domain") {
      queryClient.invalidateQueries({
        queryKey: ["domains", { layer_id: parentId }],
      });
    } else if (childType === "term") {
      if (parentType === "domain") {
        queryClient.invalidateQueries({
          queryKey: ["terms", { domain_id: parentId }],
        });
      } else if (parentType === "term") {
        queryClient.invalidateQueries({
          queryKey: ["terms", { parent_term_id: parentId }],
        });
      }
    }
  };

  const handleSuccess = (child: any) => {
    setIsModalOpen(false);

    // Invalidate queries to refresh the UI
    invalidateRelatedQueries(parentType, parentId, childType);

    if (onSuccess) {
      onSuccess(child);
    }
  };

  const getModalTitle = () => {
    if (childType === "domain") {
      return `Create Domain in Layer: ${parentObject.title}`;
    } else {
      return `Create Term in ${parentType === "domain" ? "Domain" : "Parent Term"}: ${parentObject.title}`;
    }
  };

  const renderForm = () => {
    if (childType === "domain" && parentType === "layer") {
      return (
        <DomainForm
          onSuccess={handleSuccess}
          parentLayerId={parentId}
          parentLayer={parentObject as StructureNode}
          mode="child"
        />
      );
    } else if (childType === "term") {
      if (parentType === "domain") {
        return (
          <TermForm
            onSuccess={handleSuccess}
            parentDomainId={parentId}
            parentDomain={parentObject as StructureNode}
            mode="child"
          />
        );
      } else if (parentType === "term") {
        return (
          <TermForm
            onSuccess={handleSuccess}
            parentTermId={parentId}
            parentTerm={parentObject as StructureNode}
            mode="child"
          />
        );
      }
    }

    return <div>Invalid configuration</div>;
  };

  return (
    <>
      <Button
        color="gray"
        size={size}
        onClick={() => setIsModalOpen(true)}
        className={className}
      >
        <Plus className="mr-1 h-4 w-4" />
        Add
      </Button>

      <CreateChildModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={getModalTitle()}
      >
        {renderForm()}
      </CreateChildModal>
    </>
  );
};
