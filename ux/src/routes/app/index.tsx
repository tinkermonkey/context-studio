import { createFileRoute } from "@tanstack/react-router";
import {
  Alert,
} from "flowbite-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";

export const Route = createFileRoute("/app/")({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Context</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle>Welcome</CsMainTitle>
        <Alert color="indigo">
          This is a placeholder for the app route. Replace with your actual app
          content.
        </Alert>
      </CsMain>
    </>
  );
}
