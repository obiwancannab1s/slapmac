To set a real application icon for SlapMac.app:

1. Place your PNG at the project root named `slapapp.png` (you already did).
2. Run the helper to convert it to an ICNS file:

   cd "$(dirname "$0")/../.." && SlapMac.app/Contents/Resources/make_icon.sh

3. After `slapapp.icns` is created inside `SlapMac.app/Contents/Resources/`, macOS should show the icon for the bundle. You may need to clear Finder cache or right-click -> Get Info to update.

Notes:
- `iconutil` and `sips` are macOS CLI tools available by default on macOS.
- If you prefer, you can manually create an `.icns` using third-party tools.
