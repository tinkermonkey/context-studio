# Context Studio UX

Front-end code for the Context Studio app. This is front-end code only, the back-end is in a separate repository.

## Technology Stack
- **Language**: TypeScript
- **Platform**: Expo
- **Framework**: React
- **Components**: Gluestack-UI V2
- **CSS Framework**: Tailwind CSS (via Nativewind)
- **Icons**: Lucide React Native

## Best Practices

### Code Structure
```text
/
├── .env                            # Dev environment variables (not in git)
├── .env.example                    # Environment variables example (in git)
├── .env.production                 # Production environment variables (not in git, very sensitive)
├── app.json                        # Expo app config
├── global.css                      # Global tailwind directives for nativewind
├── metro.config.js                 # Metro build config for Expo
├── nativewind-env.d.ts             # Nativewind typescript bindings
├── README.md                       # Project documentation
├── tailwind.config.js              # Tailwind configuration
├── tsconfig.json                   # Typescript config
│
├── android/                        # Android app build files
├── ios/                            # iOS app build files
│
├── app/                            # Expo app
│   ├── _layout.tsx                 # Global Expo layout
│   ├── +html.tsx                   # Global Expo html configuration for web clients
|
├── assets/                         # Static assets
│   ├── fonts/                      # Fonts
│   ├── Icons/                      # Custom icons not provided by lucide-react-native
│   └── images/                     # Custom images used in the app
|
├── components/                    # Reusable components
│   ├── common/                     # Common components used across the app
│   ├── custom/                     # Components specific to the Context Studio
│   └── ui/                         # UI components from gluestack-ui
|
├── constants/                      # Static data elements used throughout the app
│   └── Colors.ts                   # Theme colors
│
├── hooks/                          # React hooks
│   ├── useColorScheme.ts           # Color scheme hook
│   ├── useColorScheme.web.ts       # Color scheme hook for web
│   └── useThemeColors.ts           # Expo hook for themeing
│
├── node_modules/                   # Ignore this, managed by npm
```

### UI Architecture

1. **React Native**: All UX must be compatible with `react-native`, native HTML is not permissible except in platform specific (web-only) components

2. **Gluestack-UI V2**: gluestack-ui v2 components should be used for layout

3. **Responsive Layout**: A single UX will be used for desktop, tablet, and phones. Where possible, handle the responsiveness in the layout. Where needed, ensure the styling is responsive.

4. **Promote User Focus**: UX should be clean and focused without extraneous elements and decoration

5. **Error Handling**: Implement error catching within user workflows utilizing tools like useButterToast to communicate errors

6. **Asynchronous**: Where possible user interactions should be asynchronous to maintain performance and statelessness

### Testing and Reliability

3. **Graceful Degradation**: Implement fallback strategies when components fail

4. **Comprehensive Unit Tests**: Test individual components and functions in isolation where possible

5. **End-to-End Testing**: Create scenarios that test the full user journey

6. **Good Logging**: Make sure all files have good logging.