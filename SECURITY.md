# Security Policy

## Reporting a Vulnerability

If you believe you have found a security vulnerability in VoucherBot, please **do not open a public GitHub issue**. Public disclosure of a vulnerability before it is patched puts all users of the project at risk.

Instead, report it through one of the following private channels:

### Option 1 — GitHub Private Vulnerability Reporting

Use GitHub's built-in private reporting tool:

👉 [Report a vulnerability](../../security/advisories/new)

This keeps the report confidential and allows us to discuss and resolve the issue before any public disclosure.

### Option 2 — Email

Send a private email to:

📧 **devathmaj@gmail.com**

Please include as much detail as possible (see [What to Include](#what-to-include) below).

---

## What to Include

A good vulnerability report helps resolve the issue faster. Please try to include:

- A clear description of the vulnerability and its potential impact
- The component or file(s) affected (e.g. `http_policy.py`, `reddit/client.py`, `.env` handling)
- Steps to reproduce or a proof-of-concept
- Any suggested fixes or mitigations, if you have them

---

## Response Time

This is a solo-maintained open source project. I will do my best to respond as quickly as possible, but **I cannot guarantee a specific response time.** I appreciate your patience.

---

## Scope

The following are considered in scope for security reports:

- Exposure or leakage of API keys, database credentials, or other secrets
- Vulnerabilities in how environment variables are handled or logged
- Authentication or authorisation bypasses in the API layer
- Issues in the HTTP policy layer that could allow unintended external requests
- Dependency vulnerabilities with a clear, exploitable impact on this project

The following are **out of scope:**

- Vulnerabilities in third-party services (Render, Supabase, Resend, Groq, Reddit, etc.) — report those directly to the respective service
- Issues that require physical access to the deployment environment
- Social engineering attacks

---

## Disclosure Policy

Once a reported vulnerability has been confirmed and patched, I am happy to credit you in the release notes or changelog if you would like to be acknowledged. Please let me know your preferred name or handle when reporting.

I ask that you give reasonable time for the issue to be resolved before any public disclosure.