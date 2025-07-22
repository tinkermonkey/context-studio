/**
 * Example Layer List Component
 *
 * Example component showing how to use the API client
 */

import React from "react"
import { VStack } from "../ui/vstack"
import { HStack } from "../ui/hstack"
import { Button, ButtonText } from "../ui/button"
import { Text } from "../ui/text"
import { Spinner } from "../ui/spinner"
import { useLayers, useCreateLayer, useDeleteLayer } from "../../api/hooks/layers"
import { handleApiError } from "../../api/errors/errorHandlers"
import type { components } from "../../api/client/types"

type LayerCreate = components["schemas"]["LayerCreate"]

export const LayerList: React.FC = () => {
  const { data: layers, isLoading, error, refetch } = useLayers()
  const createLayer = useCreateLayer()
  const deleteLayer = useDeleteLayer()

  const handleCreate = async () => {
    try {
      const newLayer: LayerCreate = {
        title: "New Layer",
        definition: "A new layer for testing",
        primary_predicate: "test",
      }

      await createLayer.mutateAsync(newLayer)
      // Success is handled by the mutation onSuccess callback
    } catch (error) {
      handleApiError(error)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteLayer.mutateAsync(id)
      // Success is handled by the mutation onSuccess callback
    } catch (error) {
      handleApiError(error)
    }
  }

  if (isLoading) {
    return (
      <VStack className="flex-1 justify-center items-center">
        <Spinner size="large" />
        <Text className="mt-4">Loading layers...</Text>
      </VStack>
    )
  }

  if (error) {
    return (
      <VStack className="flex-1 justify-center items-center">
        <Text className="text-red-500 mb-4">Error loading layers</Text>
        <Button onPress={() => refetch()}>Retry</Button>
      </VStack>
    )
  }

  return (
    <VStack className="flex-1 p-4">
      <HStack className="justify-between items-center mb-4">
        <Text className="text-xl font-bold">Layers</Text>
        <Button onPress={handleCreate} disabled={createLayer.isPending}>
          <ButtonText>{createLayer.isPending ? "Creating..." : "Create Layer"}</ButtonText>
        </Button>
      </HStack>

      <VStack space="md">
        {layers?.map((layer) => (
          <HStack key={layer.id} className="p-4 border border-gray-200 rounded-lg justify-between items-center">
            <VStack className="flex-1">
              <Text className="font-semibold">{layer.title}</Text>
              {layer.definition && <Text className="text-gray-600">{layer.definition}</Text>}
            </VStack>
            <Button variant="outline" size="sm" onPress={() => handleDelete(layer.id)} disabled={deleteLayer.isPending}>
              <ButtonText>
                {deleteLayer.isPending && deleteLayer.variables?.id === layer.id
                  ? "Deleting..."
                  : "Delete"}
              </ButtonText>
            </Button>
          </HStack>
        ))}
      </VStack>

      {layers?.length === 0 && (
        <VStack className="flex-1 justify-center items-center">
          <Text className="text-gray-500">No layers found</Text>
        </VStack>
      )}
    </VStack>
  )
}
