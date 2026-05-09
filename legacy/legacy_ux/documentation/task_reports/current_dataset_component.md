# Current Dataset Card Component

A Flowbite-React card component that displays information about the currently active dataset in the Context Studio application.

## Features

- **Real-time Data**: Uses React Query to fetch and display the current active dataset
- **Responsive Design**: Built with Tailwind CSS for responsive layouts
- **Loading States**: Shows spinner while loading data
- **Error Handling**: Displays appropriate messages when no dataset is active or when errors occur
- **Rich Metrics**: Displays dataset statistics including layers, domains, terms, and relationships
- **Action Buttons**: Provides quick navigation to dataset management and data exploration

## Usage

```tsx
import { CurrentDatasetCard } from '@/components/datasets/current_dataset';

// Basic usage
<CurrentDatasetCard />

// With custom className
<CurrentDatasetCard className="max-w-lg shadow-lg" />
```

## API Integration

This component uses the new dataset API endpoints:

- `/api/datasets/active` - Gets the currently active dataset information

The component automatically handles:

- Loading states while fetching data
- Error states when no dataset is active
- Cache invalidation when dataset changes

## Component Structure

The card displays:

1. **Header**: Dataset title, filename, and active status badge
2. **Metrics Grid**: Visual display of dataset statistics (layers, domains, terms, relationships)
3. **Details Section**: Metadata including dataset ID, schema version, created date, and last accessed time
4. **Action Buttons**: Quick links to dataset management and data exploration

## Dependencies

- `@tanstack/react-query` - For data fetching and caching
- `flowbite-react` - For UI components (Card, Badge, Button, Spinner)
- `lucide-react` - For icons
- `@tanstack/react-router` - For navigation links

## Styling

The component uses Tailwind CSS classes and follows the existing design patterns in the Context Studio application. It supports both light and dark themes automatically.
