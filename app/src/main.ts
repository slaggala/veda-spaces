import './design-system/tokens.css';
import './design-system/components.js';
import './core/authz/can.js';
import { session } from './core/auth/session.js';
import { installGlobalHandlers } from './core/telemetry/telemetry.js';
import { siteSignOutGuard } from './modules/site/sign-out.js';
import './shell/app.js';

installGlobalHandlers();
// Unsent site captures are offered a sync before sign-out (B1-PE-02). Wired here, not in the lazily loaded site
// module, so it also runs in a tab that never opened a site page; a device that never used site capture sees nothing.
session.addLogoutGuard(siteSignOutGuard);
