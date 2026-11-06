# SnagForge Angular front end

An offline Angular 22 desktop interface. Capture, recording, clipboard, OCR and file operations connect to the native Python engine through Qt WebChannel.

The checked-in `dist/` build lets desktop users run the app without Node.js. Contributors can run `npm ci` and `npm run build` here. Source is in `src/`.

Use Node.js 24 LTS. `npm run preview` opens an interface-only preview; desktop capture requires the native application.
