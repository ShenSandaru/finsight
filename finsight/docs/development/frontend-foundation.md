# FinSight Phase 11.1 Frontend Foundation & Design System

## 1. Overview & Objectives

Phase 11.1 establishes the production-grade **Next.js frontend application foundation** for the FinSight AI investment research copilot. It implements strict TypeScript configurations, institutional financial design tokens, accessible UI components, reactive state stores, testing frameworks, and centralized API client abstractions without touching any backend logic or contracts.

---

## 2. Frontend Technology Stack

| Layer | Selected Library / Tool | Configuration / Role |
|---|---|---|
| **Framework** | Next.js 14.2 (App Router) | React Server Components, client boundaries, metadata, route handling |
| **Language** | TypeScript 5.7+ | Strict mode (`strict: true`, zero untyped `any` leaks) |
| **Styling** | Tailwind CSS 3.4 + CSS Variables | HSL design tokens, financial semantic variants, dark/light theme switching |
| **Component Primitives** | shadcn/ui + Radix UI + Lucide Icons | Headless accessible components (Button, Badge, Card, Input, Textarea, Table, Skeleton, Tooltip, Dialog, Separator) |
| **Server State** | TanStack Query v5 | QueryClient with sensible caching and non-aggressive retry logic |
| **Client UI State** | Zustand 5.0 | Lightweight `useUiStore` managing sidebar, document selection, and citation drawer |
| **Forms & Validation** | React Hook Form 7.54 + Zod 3.24 | Schema-first client validation |
| **Testing Foundation** | Vitest 2.1 + React Testing Library + jsdom | Fast unit/integration test runner with DOM assertions |
| **Design Direction** | Taste Skill Rules | Professional institutional palette (Slate/Navy), high information density, dual-channel financial indicators (color + directional glyph) |

---

## 3. Directory Structure

```
frontend/
├── app/
│   ├── layout.tsx            # Root layout with fonts, metadata, and Providers wrapper
│   ├── page.tsx              # Minimal design system verification page
│   ├── providers.tsx         # TanStack QueryClientProvider & NextThemesProvider
│   ├── globals.css           # Institutional financial HSL design tokens & utility layers
│   ├── loading.tsx           # Global loading boundary
│   ├── error.tsx             # Route-level error boundary
│   ├── global-error.tsx      # Critical root-level error boundary
│   └── not-found.tsx         # 404 handler for missing research views
├── components/
│   └── ui/                   # Reusable accessible shadcn/ui components
│       ├── badge.tsx
│       ├── button.tsx
│       ├── card.tsx
│       ├── dialog.tsx
│       ├── input.tsx
│       ├── separator.tsx
│       ├── skeleton.tsx
│       ├── table.tsx
│       ├── textarea.tsx
│       └── tooltip.tsx
├── lib/
│   ├── api/
│   │   └── client.ts         # Centralized API client with normalized ApiError
│   └── utils.ts              # cn helper & financial formatters (currency, %, ratio)
├── stores/
│   └── ui-store.ts           # Zustand store for UI toggles & document selection
├── tests/
│   ├── setup.ts              # Vitest test environment configuration
│   └── foundation.test.tsx   # Rendering and utility verification test suite
├── .env.example              # Browser-safe environment documentation
├── components.json           # shadcn configuration
├── next.config.js            # Next.js production build configuration
├── package.json              # Dependency manifest & script definitions
├── postcss.config.js         # PostCSS Tailwind plugins
├── tailwind.config.js        # Extended design tokens & financial colors
├── tsconfig.json             # Strict TypeScript configuration with @/* path aliases
└── vitest.config.ts          # Test runner configuration
```

---

## 4. Institutional Design Tokens & Typography

Adhering to Taste Skill principles, FinSight avoids "generic AI dashboard" clichés (neon gradients, excessive glassmorphism, decorative blobs). The palette is tuned for high-contrast, institutional clarity:

- **Primary**: Deep Navy Blue (`hsl(221 83% 53%)` in light mode, `hsl(217 91% 60%)` in dark mode).
- **Financial Semantics**:
  - `financePositive`: Emerald green (`↑ +14.5%`)
  - `financeNegative`: Muted rose red (`↓ -3.8%`)
  - `financeWarning`: Amber gold (`⚠`)
  - `financeNeutral`: Slate gray (`—`)
- **Typography**:
  - **Sans**: `Inter` (UI elements, headers, analytical narrative)
  - **Mono**: `JetBrains Mono` (financial tables, currency figures, code excerpts)
  - **Tabular Numbers**: `.font-tabular-nums` ensuring precise vertical alignment of decimal points across financial statement rows.

---

## 5. Security Boundaries

- **Browser Isolation**: Only `NEXT_PUBLIC_API_URL` is exposed to the browser.
- **Zero Credential Exposure**: Backend keys (Gemini API key, PostgreSQL credentials, Redis password) remain strictly on the backend server environment.

---

## 6. What Phase 11.1 Does NOT Contain

- No feature page implementations (Dashboard, Documents, Research Chat, Citation Inspector, Reports).
- No backend route or database schema modifications.
- Feature implementations will commence sequentially starting in **Phase 11.2 (API Client & Backend Type Integration)**.
