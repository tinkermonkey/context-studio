import React from "react";
import { Modal, ModalHeader, ModalBody } from "flowbite-react";

interface CreateChildModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export const CreateChildModal: React.FC<CreateChildModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
}) => {
  return (
    <Modal 
      show={isOpen} 
      onClose={onClose} 
      size="lg"
      role="dialog"
      aria-labelledby="modal-title"
      aria-modal="true"
    >
      <ModalHeader>
        <h2 id="modal-title">{title}</h2>
      </ModalHeader>
      <ModalBody>
        {children}
      </ModalBody>
    </Modal>
  );
};
