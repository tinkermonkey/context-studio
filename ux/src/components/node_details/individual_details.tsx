import React from "react";
import { Spinner, Modal, ModalHeader, ModalBody } from "flowbite-react";
import { Hash, Edit3 } from "lucide-react";
import type { components } from "@/api/client/types";
import { renderShortDateTime } from "@/utils/renderers";
import {
  CsSidebar,
  CsSidebarTitle,
  CsSidebarSection,
} from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle, CsMainHeader } from "@/components/layout/cs_main";
import { IndividualForm } from "@/components/forms/individual_form";
import { useOntologyClasses } from "@/api/hooks/ontologyClasses";
import { useIndividualInheritedProperties } from "@/api/hooks/individuals";

type IndividualResponse = components["schemas"]["IndividualResponse"];
type DataPropertyValueResponse = components["schemas"]["DataPropertyValueResponse"];
type ClassResponse = components["schemas"]["ClassResponse"];

interface IndividualDetailsProps {
  individual: IndividualResponse;
  onUpdate?: (updated: IndividualResponse) => void;
}

export const IndividualDetails: React.FC<IndividualDetailsProps> = ({
  individual,
  onUpdate,
}) => {
  const [isEditOpen, setIsEditOpen] = React.useState(false);
  const { data: availableClasses = [] } = useOntologyClasses();
  const {
    data: inheritedProperties = [],
    isLoading: inheritedPropertiesLoading,
  } = useIndividualInheritedProperties(individual.id);

  // Get the class objects for this individual
  const parentClasses: ClassResponse[] = (individual.class_ids ?? [])
    .map((id) => availableClasses.find((c) => c.id === id))
    .filter((c) => c !== undefined) as ClassResponse[];

  const handleEditSuccess = (updated: IndividualResponse) => {
    setIsEditOpen(false);
    if (onUpdate) onUpdate(updated);
  };

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Individual Details</CsSidebarTitle>
        <CsSidebarSection>
          <div className="space-y-4">
            <div>
              <h3 className="font-semibold text-gray-700">ID</h3>
              <p className="break-all text-sm text-gray-600">{individual.id}</p>
            </div>
            {parentClasses.length > 0 && (
              <div>
                <h3 className="font-semibold text-gray-700">Parent Classes</h3>
                <ul className="space-y-1 text-sm text-gray-600">
                  {parentClasses.map((cls) => (
                    <li key={cls.id}>{cls.title}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </CsSidebarSection>
      </CsSidebar>

      <CsMain>
        <CsMainHeader>
          <div className="flex items-center justify-between">
            <CsMainTitle icon={Hash}>{individual.title}</CsMainTitle>
            <button
              onClick={() => setIsEditOpen(true)}
              className="flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
              title="Edit individual"
            >
              <Edit3 className="h-4 w-4" />
              Edit
            </button>
          </div>
        </CsMainHeader>

        <div className="space-y-6">
          {/* Description Section */}
          {individual.description && (
            <section data-testid="individual-detail-description">
              <h2 className="mb-2 text-lg font-semibold">Description</h2>
              <p className="text-gray-700">{individual.description}</p>
            </section>
          )}

          {/* Parent Classes Section */}
          <section data-testid="individual-classes-section">
            <h2 className="mb-4 text-lg font-semibold">Parent Classes</h2>
            {parentClasses.length === 0 ? (
              <p className="text-gray-500">No parent classes assigned</p>
            ) : (
              <div className="space-y-2">
                {parentClasses.map((cls, index) => (
                  <div
                    key={cls.id}
                    className="rounded border border-gray-200 bg-gray-50 p-4"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="font-semibold">{cls.title}</div>
                        {cls.description && (
                          <p className="mt-1 text-sm text-gray-600">
                            {cls.description}
                          </p>
                        )}
                        <div className="mt-2 text-xs text-gray-500">
                          <span className="inline-block rounded bg-gray-200 px-2 py-1">
                            Order: {index + 1}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Inherited Properties Section */}
          <section data-testid="inherited-properties-section">
            <h2 className="mb-4 text-lg font-semibold">Inherited Properties</h2>
            {inheritedPropertiesLoading ? (
              <Spinner />
            ) : inheritedProperties.length === 0 ? (
              <p className="text-gray-500">No inherited properties</p>
            ) : (
              <div className="space-y-2">
                {inheritedProperties.map((prop, index) => (
                  <div
                    key={`${prop.property_identifier}-${index}`}
                    className="rounded border border-gray-200 bg-white p-4"
                    data-testid="inherited-properties-row"
                  >
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <div className="text-xs font-medium text-gray-500 uppercase">
                          Property
                        </div>
                        <div className="font-medium">{prop.property_identifier}</div>
                      </div>
                      <div>
                        <div className="text-xs font-medium text-gray-500 uppercase">
                          Value
                        </div>
                        <div className="text-gray-700">
                          {typeof prop.value === "object"
                            ? JSON.stringify(prop.value)
                            : String(prop.value)}
                        </div>
                      </div>
                    </div>
                    {prop.datatype && (
                      <div className="mt-2 text-xs text-gray-500">
                        Type: {prop.datatype}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Metadata Section */}
          <section className="border-t pt-4">
            <h3 className="mb-2 font-semibold text-gray-700">Metadata</h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-600">Created: </span>
                <span className="font-medium">
                  {individual.created_at
                    ? renderShortDateTime(individual.created_at)
                    : "N/A"}
                </span>
              </div>
              <div>
                <span className="text-gray-600">Modified: </span>
                <span className="font-medium">
                  {individual.last_modified
                    ? renderShortDateTime(individual.last_modified)
                    : "N/A"}
                </span>
              </div>
            </div>
          </section>
        </div>
      </CsMain>

      {/* Edit Modal */}
      <Modal show={isEditOpen} onClose={() => setIsEditOpen(false)} size="lg">
        <ModalHeader>Edit Individual</ModalHeader>
        <ModalBody>
          <IndividualForm
            individual={individual}
            onSuccess={handleEditSuccess}
            onCancel={() => setIsEditOpen(false)}
          />
        </ModalBody>
      </Modal>
    </>
  );
};
