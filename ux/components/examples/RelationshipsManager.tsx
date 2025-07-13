/**
 * Relationships Manager Example Component
 * 
 * Example component demonstrating the use of relationship hooks
 */

import React, { useState } from 'react';
import { View, Text, TouchableOpacity, FlatList, TextInput, Alert } from 'react-native';
import {
  useRelationships,
  useTermRelationships,
  useRelationshipsByPredicate,
  useCreateRelationship,
  useDeleteRelationship,
} from '../../api/hooks/relationships';
import { useTerms } from '../../api/hooks/terms';
import type { components } from '../../api/client/types';

type TermRelationshipOut = components['schemas']['TermRelationshipOut'];

interface RelationshipsManagerProps {
  selectedTermId?: string;
}

export function RelationshipsManager({ selectedTermId }: RelationshipsManagerProps) {
  const [selectedPredicate, setSelectedPredicate] = useState('');
  const [newSourceTermId, setNewSourceTermId] = useState('');
  const [newTargetTermId, setNewTargetTermId] = useState('');
  const [newPredicate, setNewPredicate] = useState('');

  // Queries
  const { data: allRelationships, isLoading: allRelationshipsLoading } = useRelationships();
  const { data: termRelationships, isLoading: termRelationshipsLoading } = useTermRelationships(
    selectedTermId || '',
    !!selectedTermId
  );
  const { data: predicateRelationships, isLoading: predicateRelationshipsLoading } = useRelationshipsByPredicate(
    selectedPredicate,
    !!selectedPredicate
  );
  const { data: terms } = useTerms();

  // Mutations
  const createRelationshipMutation = useCreateRelationship();
  const deleteRelationshipMutation = useDeleteRelationship();

  // Determine which relationships to display
  let displayRelationships: TermRelationshipOut[] = [];
  let loadingState = false;
  let title = 'All Relationships';

  if (selectedTermId) {
    displayRelationships = termRelationships || [];
    loadingState = termRelationshipsLoading;
    title = `Relationships for Selected Term`;
  } else if (selectedPredicate) {
    displayRelationships = predicateRelationships || [];
    loadingState = predicateRelationshipsLoading;
    title = `Relationships with predicate "${selectedPredicate}"`;
  } else {
    displayRelationships = allRelationships || [];
    loadingState = allRelationshipsLoading;
    title = 'All Relationships';
  }

  const handleCreateRelationship = async () => {
    if (!newSourceTermId.trim() || !newTargetTermId.trim() || !newPredicate.trim()) {
      Alert.alert('Error', 'Please fill in all fields');
      return;
    }

    if (newSourceTermId === newTargetTermId) {
      Alert.alert('Error', 'Source and target terms must be different');
      return;
    }

    try {
      await createRelationshipMutation.mutateAsync({
        source_term_id: newSourceTermId.trim(),
        target_term_id: newTargetTermId.trim(),
        predicate: newPredicate.trim(),
      });
      
      setNewSourceTermId('');
      setNewTargetTermId('');
      setNewPredicate('');
      Alert.alert('Success', 'Relationship created successfully');
    } catch (error) {
      Alert.alert('Error', 'Failed to create relationship');
      console.error('Create relationship error:', error);
    }
  };

  const handleDeleteRelationship = async (id: string, relationship: TermRelationshipOut) => {
    const sourceTermTitle = terms?.find(t => t.id === relationship.source_term_id)?.title || 'Unknown';
    const targetTermTitle = terms?.find(t => t.id === relationship.target_term_id)?.title || 'Unknown';
    
    Alert.alert(
      'Confirm Delete',
      `Are you sure you want to delete the relationship:\n"${sourceTermTitle}" ${relationship.predicate} "${targetTermTitle}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteRelationshipMutation.mutateAsync(id);
              Alert.alert('Success', 'Relationship deleted successfully');
            } catch (error) {
              Alert.alert('Error', 'Failed to delete relationship');
              console.error('Delete relationship error:', error);
            }
          },
        },
      ]
    );
  };

  const getTermTitle = (termId: string): string => {
    return terms?.find(t => t.id === termId)?.title || `Term ID: ${termId}`;
  };

  const uniquePredicates = Array.from(
    new Set(allRelationships?.map(r => r.predicate) || [])
  ).sort();

  const renderRelationship = ({ item }: { item: TermRelationshipOut }) => (
    <View style={{ padding: 16, borderBottomWidth: 1, borderBottomColor: '#eee' }}>
      <View style={{ marginBottom: 8 }}>
        <Text style={{ fontSize: 16 }}>
          <Text style={{ fontWeight: 'bold' }}>{getTermTitle(item.source_term_id)}</Text>
          <Text style={{ color: '#007AFF', fontStyle: 'italic' }}> {item.predicate} </Text>
          <Text style={{ fontWeight: 'bold' }}>{getTermTitle(item.target_term_id)}</Text>
        </Text>
      </View>
      
      <Text style={{ fontSize: 12, color: '#999', marginBottom: 8 }}>
        Created: {new Date(item.created_at).toLocaleDateString()}
      </Text>
      
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <TouchableOpacity
          style={{ backgroundColor: '#FF3B30', padding: 8, borderRadius: 4 }}
          onPress={() => handleDeleteRelationship(item.id, item)}
        >
          <Text style={{ color: 'white', fontSize: 12 }}>Delete</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  return (
    <View style={{ flex: 1, padding: 16 }}>
      <Text style={{ fontSize: 24, fontWeight: 'bold', marginBottom: 16 }}>Relationships Manager</Text>
      
      {/* Filters */}
      <View style={{ marginBottom: 16 }}>
        <Text style={{ fontSize: 16, fontWeight: 'bold', marginBottom: 8 }}>Filter by Predicate:</Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          <TouchableOpacity
            style={{
              padding: 8,
              borderRadius: 16,
              backgroundColor: !selectedPredicate ? '#007AFF' : '#f0f0f0',
            }}
            onPress={() => setSelectedPredicate('')}
          >
            <Text style={{ color: !selectedPredicate ? 'white' : '#333' }}>All</Text>
          </TouchableOpacity>
          {uniquePredicates.map((predicate) => (
            <TouchableOpacity
              key={predicate}
              style={{
                padding: 8,
                borderRadius: 16,
                backgroundColor: selectedPredicate === predicate ? '#007AFF' : '#f0f0f0',
              }}
              onPress={() => setSelectedPredicate(predicate)}
            >
              <Text style={{ color: selectedPredicate === predicate ? 'white' : '#333' }}>
                {predicate}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Create New Relationship */}
      <View style={{ marginBottom: 16, padding: 16, backgroundColor: '#f5f5f5', borderRadius: 8 }}>
        <Text style={{ fontSize: 18, fontWeight: 'bold', marginBottom: 8 }}>Create New Relationship</Text>
        
        <Text style={{ marginBottom: 4 }}>Source Term ID:</Text>
        <TextInput
          style={{ borderWidth: 1, borderColor: '#ddd', padding: 8, borderRadius: 4, marginBottom: 8 }}
          placeholder="Enter source term ID"
          value={newSourceTermId}
          onChangeText={setNewSourceTermId}
        />
        
        <Text style={{ marginBottom: 4 }}>Predicate:</Text>
        <TextInput
          style={{ borderWidth: 1, borderColor: '#ddd', padding: 8, borderRadius: 4, marginBottom: 8 }}
          placeholder="e.g., relates_to, is_part_of, defines"
          value={newPredicate}
          onChangeText={setNewPredicate}
        />
        
        <Text style={{ marginBottom: 4 }}>Target Term ID:</Text>
        <TextInput
          style={{ borderWidth: 1, borderColor: '#ddd', padding: 8, borderRadius: 4, marginBottom: 8 }}
          placeholder="Enter target term ID"
          value={newTargetTermId}
          onChangeText={setNewTargetTermId}
        />
        
        <TouchableOpacity
          style={{
            backgroundColor: createRelationshipMutation.isPending ? '#ccc' : '#34C759',
            padding: 12,
            borderRadius: 8,
            alignItems: 'center',
          }}
          onPress={handleCreateRelationship}
          disabled={createRelationshipMutation.isPending}
        >
          <Text style={{ color: 'white', fontWeight: 'bold' }}>
            {createRelationshipMutation.isPending ? 'Creating...' : 'Create Relationship'}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Relationships List */}
      <Text style={{ fontSize: 18, fontWeight: 'bold', marginBottom: 8 }}>{title}</Text>
      
      {loadingState ? (
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <Text>Loading relationships...</Text>
        </View>
      ) : (
        <FlatList
          data={displayRelationships}
          keyExtractor={(item) => item.id}
          renderItem={renderRelationship}
          ListEmptyComponent={
            <View style={{ padding: 32, alignItems: 'center' }}>
              <Text style={{ color: '#666', textAlign: 'center' }}>
                No relationships found
              </Text>
            </View>
          }
        />
      )}
    </View>
  );
}
