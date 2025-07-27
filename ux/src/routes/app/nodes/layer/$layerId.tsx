import { createFileRoute } from '@tanstack/react-router';
import { Spinner, Alert } from 'flowbite-react';
import { useLayer } from '@/api/hooks/layers/useLayers';
import { LayerDetails } from '@/components/node_details/layer_details';

export const Route = createFileRoute('/app/nodes/layer/$layerId')({
  component: LayerDetailPage,
});

function LayerDetailPage() {
  const { layerId } = Route.useParams() as { layerId: string };
  const { data: layer, isLoading: layerLoading, error: layerError } = useLayer(layerId);

  if (layerLoading) {
    return (
      <div className="flex justify-center items-center p-8">
        <Spinner size="lg" aria-label="Loading layer..." />
        <span className="ml-3 text-lg">Loading layer...</span>
      </div>
    );
  }

  if (layerError || !layer) {
    return (
      <Alert color="failure" className="m-4">
        <span className="font-medium">Error!</span> Unable to load layer with ID: {layerId}
      </Alert>
    );
  }
  
  return <LayerDetails layer={layer} />;
}
