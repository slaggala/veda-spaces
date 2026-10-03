# Manual accessibility verification script (OI-RM-5, RR-18, IR-37)

The automated checks cover what a machine can see: axe-core scans of 16 screens and states in the browser E2E
(`app/e2e/axe.e2e.mjs`, 0 serious or critical), the component tests with axe (`app/test/a11y.test.ts`), and the
token contrast test (58 pairs, both themes). They cannot hear what a screen reader announces, judge whether focus
order makes sense, or check reflow at 200 % zoom. This script covers that. It is the evidence for OI-RM-5 and the
manual part of UI-016 (09 §5, AX-01…AX-10). Firefox and WebKit **automated** legs are a separate item (OI-RM-2).

- **Who:** someone other than the author of the code under test, who uses the screen reader regularly or has
  completed its tutorial.
- **Where:** the staging build once it exists. Until then, a local release build of the same commit is acceptable as
  rehearsal; its notes do not close OI-RM-5.
- **Data:** the seeded staging fixtures (a Founder with MFA, a Sales user, at least 10 leads across statuses). Never
  production data.
- **Record:** one copy of the table in §6 per platform, filled in, plus short notes for every FAIL. Store it under
  `docs/release-evidence/OI-RM-5/` through a pull request (no personal data, no credentials).

## 1. Platforms

| # | Screen reader | Browser | OS | Viewport |
|---|---|---|---|---|
| P1 | NVDA (current release) | Firefox (current) | Windows 11 | desktop |
| P2 | NVDA | Chrome (current) | Windows 11 | desktop |
| P3 | VoiceOver | Safari | macOS (current) | desktop |
| P4 | VoiceOver | Safari | iOS (current) | 390 × 844 |
| P5 | none (keyboard and zoom only) | Chrome | any | 320 px wide, and 1280 px at 200 % and 400 % zoom |

Run sections 2–4 on P1 and P3, and the starred (★) checks on P2 and P4. Run §5 on P5.

## 2. Sign-in, MFA and step-up (AX-03, AX-04, AX-07)

| ID | Steps | Expected |
|---|---|---|
| A1 ★ | Open `/login`. Tab through the form. | Fields are announced with their labels ("Email", "Password"); the password field reports its purpose; "Sign in" is a button. |
| A2 ★ | Submit with both fields empty. | An error summary is announced (alert) and receives focus; each field reports "invalid" and its message. |
| A3 | Sign in with a wrong password. | The failure is announced once, without moving focus off the form. |
| A4 ★ | Sign in correctly. On the MFA page, check the code field. | Focus lands on the code field; it is announced as a numeric code input; the page states when the request expires. |
| A5 | Enter a wrong code. | "That code didn't work. N attempts left." is announced (assertive); the field is cleared and keeps focus. |
| A6 | Wait on the MFA page until one minute before expiry (5-minute challenge). | "…expires in 1 minute" is announced without moving focus (polite). |
| A7 | Let it expire. | The expiry is announced; the page offers to sign in again. |
| A8 | Use "Use a recovery code" and complete the recovery page with the keyboard only. | Every step operable and announced; errors as in A2. |
| A9 | Signed in, wait more than 10 minutes, then try a protected action (for example, revoke a user's sessions). | "Confirm it's you" opens as a labelled modal dialog; focus is in the code field; the help text states the expiry ("expires in 5 minutes"). |
| A10 | In that dialog, enter a wrong code. | "That code didn't work. N attempts left." announced; field cleared and focused (RR-18). |
| A11 | Leave the dialog open until one minute before expiry, then until expiry. | The polite warning, then the expiry message (assertive); Confirm and the field become unavailable; Cancel closes and returns focus to the control that opened it (RR-18). |
| A12 | Press Escape in the dialog. | The dialog closes; focus returns to the control that opened it; the action is not performed. |

## 3. Workspace navigation (AX-01, AX-02, RR-18)

| ID | Steps | Expected |
|---|---|---|
| B1 ★ | After sign-in, Tab from the top of the page. | A logical order: main navigation, search, notifications, account menu, then the page. The focus ring is always visible and never hidden by the sticky header (AX-02). |
| B2 | Navigate between pages from the side navigation. | The new page title is announced, and focus moves to the page content (`main`). The current link is announced as current. |
| B3 ★ | Press Ctrl+K (⌘K on macOS). | The "Jump to" dialog opens; focus is in an input announced as a combobox ("Search leads and pages"), with the number of results announced (RR-18). |
| B4 | Type part of a lead's name. Use Down and Up arrows. | Focus stays in the input; each arrow press announces the highlighted result ("Anita Reddy, VS-L-…"); the result count is announced after typing (RR-18). |
| B5 | Press Enter on a highlighted lead. | The dialog closes and the lead opens; its title is announced. |
| B6 | Type a term with no match. | "0 results" is announced. |
| B7 ★ | Open the account menu with Enter. | The button reports "expanded"; the menu shows the name, "Profile" and "Sign out" (RR-18). |
| B8 | With the menu open, press Escape (focus on the button), then reopen and press Escape from "Profile". | Both times the menu closes and focus is on the account-menu button (RR-18). |
| B9 | Reopen the menu and Tab past "Sign out". | The menu closes as focus leaves it (RR-18). |
| B10 | Reopen the menu and click elsewhere on the page. | The menu closes (RR-18). |
| B11 | Open the notifications tray. | Opened and closed with the keyboard; new notifications are announced politely; Escape closes it. |

## 4. Leads (AX-01, AX-03, AX-09, RR-18)

| ID | Steps | Expected |
|---|---|---|
| C1 ★ | On `/leads`, move through the list with the keyboard. | Columns have headers; each row's lead link is reachable; filters are labelled and the active filter chips can be cleared by keyboard. |
| C2 | Switch to the board view. On a card, use "Move to…". | The "Move to…" control is reachable and labelled; choosing a status opens the labelled status dialog (AX-09: keyboard alternative to drag). |
| C3 ★ | Create a lead with the keyboard; submit it once with a required field empty. | Error summary announced and focused; fields linked to their messages; on success a toast is announced. |
| C4 ★ | Open a lead. Find the status stepper. | The stepper is announced as a list with the current status marked as current; at 360 px it is a focusable, labelled region that scrolls with the arrow keys (IR-37). |
| C5 | Use "Move to …" on the lead and complete the dialog. | The dialog is labelled with the transition; required fields announced; focus returns afterwards; the change is announced. |
| C6 ★ | Reach the tabs "Timeline / Notes / History". | Announced as a tab list named "Lead records"; each tab announced as "tab, N of M, selected" when selected (RR-18). |
| C7 | Press Right, Left, Home and End on the tabs. | Selection and focus move together; hidden tabs are skipped (RR-18). |
| C8 | From the selected tab, press Tab. | Focus enters the tab panel; the screen reader announces it as the panel for the selected tab (for example "Notes, tab panel"). This wiring is what RR-18 fixed. |
| C9 | Log an activity and add a note with the keyboard. | Dialogs labelled; errors announced; focus returns to the opener. |
| C10 | On Profile and on Users → a user → the drawer, repeat C6–C8. | Tab lists named "Account sections" and "User sections"; panels wired as in C8. |
| C11 | On a lead whose consent was withdrawn, open the lead. | The "Do not contact" banner is announced. |

## 5. Zoom, reflow, targets and motion (AX-06, AX-10)

| ID | Steps | Expected |
|---|---|---|
| D1 | At 320 px wide (P5): login, MFA, lead list, lead detail, activity dialog. | No horizontal scrolling of the page (the status stepper and tables may scroll inside their own labelled regions); nothing cut off; all actions reachable. |
| D2 | At 1280 px with 200 % zoom, then 400 % zoom: the same screens. | Same as D1; text does not overlap; dialogs fit and scroll. |
| D3 | Check interactive targets on the 320 px screens. | Targets at least 44 × 44 px (minimum 24 × 24 px with spacing, WCAG 2.5.8). |
| D4 | Turn on "reduce motion" in the OS; reload the workspace and the public site. | No animated transitions; the site shows every section at full opacity. |
| D5 | Check the page language and a date. | The page language is `en-IN`; dates and times are in the user's time zone. |
| D6 | On the public site's enquiry form (staging site): submit it empty, then the success and fallback panels. | Errors announced and linked; the success or fallback panel receives focus and is announced; the honeypot field is never reached or announced (AX-08). |
| D7 | On the public site, Tab through links. | The focus ring is visible. **Known failure:** FC-15 (focus ring below 3:1); record it, do not stop. |

## 6. Record

Fill one table per platform. `Result`: PASS, FAIL or N/A (with the reason).

| Platform | Build commit | Date | Tester | Screen reader / browser versions |
|---|---|---|---|---|
| | | | | |

| ID | Result | Notes (what was announced, what went wrong) |
|---|---|---|
| A1 | | |
| … | | |

**Pass rule:** OI-RM-5 closes when every check is PASS or N/A on P1 and P3, every ★ check is PASS or N/A on P2
and P4, §5 is PASS on P5, and every FAIL has a tracked item. Known failures (FC-15) must be fixed or accepted by the
owner before production.
