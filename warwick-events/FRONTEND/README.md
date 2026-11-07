# common

A simple Warwick campus frontend in HTML, CSS and JavaScript. No dependencies or build step.

## run locally

From this directory, run `npm start`, then visit http://localhost:3000. Requires Node.js.

Enter any valid email to try the demo. This is a prototype login, not authentication. The email stays in session storage for this browser tab until sign-out. The bottom navigation is discover, calendar, make an event, then settings.

Discover opens first, with a vertically snapping event feed, event details and potential clashes against your liked and signed-up events. The feed shows sample events for the next 45 days and all locally submitted events. Like an event to save it to your personal calendar, or sign up to mark yourself as going. Both actions can be toggled off, and selections persist per email in this browser. Sign-ups do not submit registrations to societies.

Use “my calendar only” to display liked and signed-up events. The daily agenda groups events as signed up, favourites, then other events; signed-up events appear only in the first group even if also liked. Clash checks compare event intervals, including overnight overlaps. New events accept a duration; older events default to 60 minutes.

Create events with a society name, category, date, time, location, description and optional HTTPS banner image URL. Events persist in this browser's local storage and appear immediately on their calendar date. All demo accounts can submit events; society president roles are not verified. Events are not shared between devices or browsers.

Click a calendar date to reveal its event banners beside the calendar (below it on mobile). Close the agenda with the cross button. Sample events are labelled separately. Category banner photographs load from Unsplash; a gradient remains if an image cannot load. Afacad loads from Google Fonts, with a sans-serif fallback when offline.

For a hackathon, this local server is enough for presenting on your laptop. A future shared demo can use static hosting. Connect real authentication and an events API before using real student data.
