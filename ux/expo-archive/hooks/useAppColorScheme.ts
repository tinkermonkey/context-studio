import { ColorModeContext } from '@/app/_layout'
import { useContext } from 'react'

/**
 * A hook to access the app's color mode state.
 * This is distinct from the device theme and is controlled by the app's UI.
 */
export function useAppColorScheme() {
  const { colorMode } = useContext(ColorModeContext);
  return colorMode;
}