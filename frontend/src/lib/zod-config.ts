import { z } from 'zod'

// The production CSP has no 'unsafe-eval'. Without this, Zod probes `new Function` on first
// use, which is caught but still reported as a CSP violation. Imported first in main.tsx,
// because imports run before main's own code and some modules build schemas on load.
z.config({ jitless: true })
