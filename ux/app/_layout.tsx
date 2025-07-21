import { Fab } from "@/components/ui/fab"
import { GluestackUIProvider } from "@/components/ui/gluestack-ui-provider"
import { ChevronLeftIcon, Icon, MoonIcon, SunIcon } from "@/components/ui/icon"
import { Pressable } from "@/components/ui/pressable"
import { ApiProvider } from "@/api/ApiProvider"
import FontAwesome from "@expo/vector-icons/FontAwesome"
import { DarkTheme, DefaultTheme, ThemeProvider } from "@react-navigation/native"
import { useFonts } from "expo-font"
import { Stack, useRouter } from "expo-router"
import * as SplashScreen from "expo-splash-screen"
import React, { useEffect } from "react"
import { Platform, StyleSheet } from "react-native"

import "../global.css"

type ColorModeType = "light" | "dark"
type ColorModeContextType = {
  colorMode: ColorModeType
  setColorMode: React.Dispatch<React.SetStateAction<ColorModeType>>
}

export const ColorModeContext = React.createContext<ColorModeContextType>({
  colorMode: "light",
  setColorMode: () => {},
})

export {
  // Catch any errors thrown by the Layout component.
  ErrorBoundary,
} from "expo-router"

// Prevent the splash screen from auto-hiding before asset loading is complete.
SplashScreen.preventAutoHideAsync()

const CustomBackButton = () => {
  const router = useRouter()

  return (
    <Pressable
      onPress={() => {
        router.back()
      }}
      className="web:ml-2 ios:-ml-2 android:mr-4">
      <Icon as={ChevronLeftIcon} size="xl" />
    </Pressable>
  )
}

export default function RootLayout() {
  const [loaded, error] = useFonts({
    SpaceMono: require("../assets/fonts/SpaceMono-Regular.ttf"),
    ...FontAwesome.font,
  })
  const [colorMode, setColorMode] = React.useState<ColorModeType>("light")

  const styles = StyleSheet.create({
    header: {
      backgroundColor: colorMode === "light" ? "#fff" : "#000",
      borderBottomColor: colorMode === "light" ? "#E6E6E6" : "#414141",
      borderBottomWidth: 1,
    },
  })

  const handleColorMode = () => {
    setColorMode((prevMode) => (prevMode === "light" ? "dark" : "light"))
  }

  const getHeaderOptions = (title: string, visible: boolean = false) => ({
    headerShown: false,
    headerTitle: title,
    headerTintColor: colorMode === "light" ? "#000" : "#fff",
    headerStyle: styles.header,
    ...(Platform.OS !== "android" && {
      headerLeft: () => <CustomBackButton />,
    }),
  })

  // Expo Router uses Error Boundaries to catch errors in the navigation tree.
  useEffect(() => {
    if (error) throw error
  }, [error])

  useEffect(() => {
    if (loaded) {
      SplashScreen.hideAsync()
    }
  }, [loaded])

  return (
    <>
      <ColorModeContext.Provider value={{ colorMode, setColorMode }}>
        <GluestackUIProvider mode={colorMode === "dark" ? "dark" : "light"}>
          <ApiProvider>
            <ThemeProvider value={colorMode === "dark" ? DarkTheme : DefaultTheme}>
              <Stack>
                <Stack.Screen name="(tabs)" options={getHeaderOptions("Thread")} />
              </Stack>
              <Fab className="bottom-10 sm:right-10 right-6 p-4 z-0" onPress={handleColorMode}>
                <Icon as={colorMode === "light" ? SunIcon : MoonIcon} className="text-typography-0" />
              </Fab>
            </ThemeProvider>
          </ApiProvider>
        </GluestackUIProvider>
      </ColorModeContext.Provider>
    </>
  )
}
