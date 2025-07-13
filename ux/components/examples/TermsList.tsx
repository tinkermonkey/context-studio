/**
 * Terms List Example Component
 * 
 * Example component demonstrating the use of terms hooks
 */

import React, { useState } from 'react';
import { View, Text, TouchableOpacity, FlatList, TextInput, Alert } from 'react-native';
import {
  useTerms,
  useTermsSearch,
  useCreateTerm,
  useUpdateTerm,
  useDeleteTerm,
} from '../../api/hooks/terms';
import type { components } from '../../api/client/types';

type TermOut = components['schemas']['TermOut'];

export function TermsList() {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingTerm, setEditingTerm] = useState<string | null>(null);
  const [newTermTitle, setNewTermTitle] = useState('');
  const [newTermDefinition, setNewTermDefinition] = useState('');

  // Queries
  const { data: terms, isLoading: termsLoading, error: termsError } = useTerms();
  const { data: searchResults, isLoading: searchLoading } = useTermsSearch(searchQuery, !!searchQuery.trim());

  // Mutations
  const createTermMutation = useCreateTerm();
  const updateTermMutation = useUpdateTerm();
  const deleteTermMutation = useDeleteTerm();

  const displayTerms = searchQuery.trim() ? searchResults : terms;

  const handleCreateTerm = async () => {
    if (!newTermTitle.trim() || !newTermDefinition.trim()) {
      Alert.alert('Error', 'Please enter both title and definition');
      return;
    }

    try {
      await createTermMutation.mutateAsync({
        title: newTermTitle.trim(),
        definition: newTermDefinition.trim(),
        domain_id: 'example-domain-id', // In real app, this would come from context or props
        layer_id: 'example-layer-id',
      });
      
      setNewTermTitle('');
      setNewTermDefinition('');
      Alert.alert('Success', 'Term created successfully');
    } catch (error) {
      Alert.alert('Error', 'Failed to create term');
      console.error('Create term error:', error);
    }
  };

  const handleUpdateTerm = async (id: string, newTitle: string) => {
    try {
      await updateTermMutation.mutateAsync({
        id,
        data: { title: newTitle.trim() },
      });
      
      setEditingTerm(null);
      Alert.alert('Success', 'Term updated successfully');
    } catch (error) {
      Alert.alert('Error', 'Failed to update term');
      console.error('Update term error:', error);
    }
  };

  const handleDeleteTerm = async (id: string, title: string) => {
    Alert.alert(
      'Confirm Delete',
      `Are you sure you want to delete "${title}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteTermMutation.mutateAsync(id);
              Alert.alert('Success', 'Term deleted successfully');
            } catch (error) {
              Alert.alert('Error', 'Failed to delete term');
              console.error('Delete term error:', error);
            }
          },
        },
      ]
    );
  };

  const renderTerm = ({ item }: { item: TermOut }) => (
    <View style={{ padding: 16, borderBottomWidth: 1, borderBottomColor: '#eee' }}>
      {editingTerm === item.id ? (
        <View>
          <TextInput
            style={{ borderWidth: 1, borderColor: '#ddd', padding: 8, marginBottom: 8 }}
            value={item.title}
            onChangeText={(text) => {
              // In a real app, you'd manage this with local state
            }}
            onSubmitEditing={(e) => handleUpdateTerm(item.id, e.nativeEvent.text)}
            onBlur={() => setEditingTerm(null)}
            autoFocus
          />
        </View>
      ) : (
        <View>
          <Text style={{ fontSize: 18, fontWeight: 'bold', marginBottom: 4 }}>
            {item.title}
          </Text>
          <Text style={{ fontSize: 14, color: '#666', marginBottom: 8 }}>
            {item.definition}
          </Text>
          <Text style={{ fontSize: 12, color: '#999', marginBottom: 8 }}>
            Version: {item.version} | Updated: {new Date(item.last_modified).toLocaleDateString()}
          </Text>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TouchableOpacity
              style={{ backgroundColor: '#007AFF', padding: 8, borderRadius: 4 }}
              onPress={() => setEditingTerm(item.id)}
            >
              <Text style={{ color: 'white', fontSize: 12 }}>Edit</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={{ backgroundColor: '#FF3B30', padding: 8, borderRadius: 4 }}
              onPress={() => handleDeleteTerm(item.id, item.title)}
            >
              <Text style={{ color: 'white', fontSize: 12 }}>Delete</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </View>
  );

  if (termsError) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 }}>
        <Text style={{ color: '#FF3B30', textAlign: 'center', marginBottom: 16 }}>
          Error loading terms: {termsError instanceof Error ? termsError.message : 'Unknown error'}
        </Text>
        <TouchableOpacity
          style={{ backgroundColor: '#007AFF', padding: 12, borderRadius: 8 }}
          onPress={() => window.location.reload()}
        >
          <Text style={{ color: 'white' }}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, padding: 16 }}>
      <Text style={{ fontSize: 24, fontWeight: 'bold', marginBottom: 16 }}>Terms</Text>
      
      {/* Search */}
      <TextInput
        style={{ borderWidth: 1, borderColor: '#ddd', padding: 12, borderRadius: 8, marginBottom: 16 }}
        placeholder="Search terms..."
        value={searchQuery}
        onChangeText={setSearchQuery}
      />
      
      {/* Create New Term */}
      <View style={{ marginBottom: 16, padding: 16, backgroundColor: '#f5f5f5', borderRadius: 8 }}>
        <Text style={{ fontSize: 18, fontWeight: 'bold', marginBottom: 8 }}>Create New Term</Text>
        <TextInput
          style={{ borderWidth: 1, borderColor: '#ddd', padding: 8, borderRadius: 4, marginBottom: 8 }}
          placeholder="Term title"
          value={newTermTitle}
          onChangeText={setNewTermTitle}
        />
        <TextInput
          style={{ borderWidth: 1, borderColor: '#ddd', padding: 8, borderRadius: 4, marginBottom: 8 }}
          placeholder="Term definition"
          value={newTermDefinition}
          onChangeText={setNewTermDefinition}
          multiline
        />
        <TouchableOpacity
          style={{
            backgroundColor: createTermMutation.isPending ? '#ccc' : '#34C759',
            padding: 12,
            borderRadius: 8,
            alignItems: 'center',
          }}
          onPress={handleCreateTerm}
          disabled={createTermMutation.isPending}
        >
          <Text style={{ color: 'white', fontWeight: 'bold' }}>
            {createTermMutation.isPending ? 'Creating...' : 'Create Term'}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Terms List */}
      {termsLoading || searchLoading ? (
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <Text>Loading terms...</Text>
        </View>
      ) : (
        <FlatList
          data={displayTerms || []}
          keyExtractor={(item) => item.id}
          renderItem={renderTerm}
          ListEmptyComponent={
            <View style={{ padding: 32, alignItems: 'center' }}>
              <Text style={{ color: '#666', textAlign: 'center' }}>
                {searchQuery.trim() ? 'No terms found matching your search' : 'No terms available'}
              </Text>
            </View>
          }
        />
      )}
    </View>
  );
}
