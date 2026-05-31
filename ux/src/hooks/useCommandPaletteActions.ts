import { useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useCommandPaletteStore, type PaletteAction } from "@/stores/commandPalette";
import { useTaxonomies } from "@/api/hooks/ontology";
import { useClasses } from "@/api/hooks/ontology";
import { useIndividuals } from "@/api/hooks/ontology";
import { useSchemes } from "@/api/hooks/ontology";

export function useCommandPaletteActions() {
  const navigate = useNavigate();
  const { registerActions, unregisterActions } = useCommandPaletteStore();

  const { data: taxonomies } = useTaxonomies();
  const { data: classes } = useClasses();
  const { data: individuals } = useIndividuals();
  const { data: schemes } = useSchemes();

  useEffect(() => {
    const dynamicActions: PaletteAction[] = [];

    if (taxonomies && taxonomies.items && taxonomies.items.length > 0) {
      taxonomies.items.slice(0, 5).forEach((taxonomy) => {
        dynamicActions.push({
          id: `taxonomy-${taxonomy.id}`,
          label: `Go to taxonomy · ${taxonomy.title}`,
          description: "Taxonomy",
          onSelect: () => {
            navigate({ to: `/app/schema/taxonomies/${taxonomy.id}` }).catch(() => {});
          },
        });
      });
    }

    if (classes && classes.items && classes.items.length > 0) {
      classes.items.slice(0, 5).forEach((classItem) => {
        dynamicActions.push({
          id: `class-${classItem.id}`,
          label: `Go to class · ${classItem.title}`,
          description: classItem.description || "Class",
          onSelect: () => {
            navigate({ to: `/app/schema/classes/${classItem.id}` }).catch(() => {});
          },
        });
      });
    }

    if (individuals && individuals.items && individuals.items.length > 0) {
      individuals.items.slice(0, 5).forEach((individual) => {
        dynamicActions.push({
          id: `individual-${individual.id}`,
          label: `Go to individual · ${individual.title}`,
          description: individual.description || "Individual",
          onSelect: () => {
            navigate({ to: `/app/data/individuals/${individual.id}` }).catch(() => {});
          },
        });
      });
    }

    if (schemes && schemes.items && schemes.items.length > 0) {
      schemes.items.slice(0, 5).forEach((scheme) => {
        dynamicActions.push({
          id: `scheme-${scheme.id}`,
          label: `Go to scheme · ${scheme.title}`,
          description: scheme.description || "Scheme",
          onSelect: () => {
            navigate({ to: `/app/schema/schemes/${scheme.id}` }).catch(() => {});
          },
        });
      });
    }

    if (dynamicActions.length > 0) {
      registerActions(dynamicActions);
    }

    return () => {
      if (dynamicActions.length > 0) {
        unregisterActions(dynamicActions.map((a) => a.id));
      }
    };
  }, [
    taxonomies,
    classes,
    individuals,
    schemes,
    registerActions,
    unregisterActions,
    navigate,
  ]);
}
