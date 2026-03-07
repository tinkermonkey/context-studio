import { useEffect, useState } from "react";

/**
 * Hook to measure and cache the navbar height
 * Returns the measured height in pixels and sets a CSS custom property
 */
export function useNavbarHeight(): number {
  const [navbarHeight, setNavbarHeight] = useState<number>(0);

  useEffect(() => {
    // Check if we have a cached value in sessionStorage
    const cachedHeight = sessionStorage.getItem("navbarHeight");
    if (cachedHeight) {
      const height = parseInt(cachedHeight, 10);
      setNavbarHeight(height);
      // Set CSS custom property
      document.documentElement.style.setProperty(
        "--navbar-height",
        `${height}px`,
      );
      return;
    }

    // Measure the navbar height
    const measureNavbar = () => {
      const navbar = document.querySelector("nav");
      if (navbar) {
        const height = navbar.clientHeight;
        setNavbarHeight(height);
        // Cache the height in sessionStorage
        sessionStorage.setItem("navbarHeight", height.toString());
        // Set CSS custom property
        document.documentElement.style.setProperty(
          "--navbar-height",
          `${height}px`,
        );
      }
    };

    // Measure after a short delay to ensure DOM is ready
    const timeoutId = setTimeout(measureNavbar, 0);

    return () => clearTimeout(timeoutId);
  }, []);

  return navbarHeight;
}
