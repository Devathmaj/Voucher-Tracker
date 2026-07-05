# VoucherBot

An intelligent certification voucher aggregator that continuously monitors community and official sources for certification discounts, free exam opportunities, beta exams, and promotional campaigns.

## Overview

VoucherBot is a Python application that automates the discovery of certification offers across the internet. Instead of manually checking dozens of websites, blogs, forums, and communities, VoucherBot continuously monitors multiple sources, filters relevant content, and identifies potential certification promotions using keyword scoring and AI-powered analysis.

The project is designed to be modular, making it easy to add new data sources and notification channels over time.

## 🚀 Deployment

Follow the steps below to deploy the project.

1. **Fork or download the repository.**

   * **Forking the repository is the recommended approach**, as the project includes a `render.yaml` file that works with Render's GitHub integration, making deployment and future updates significantly easier through automatic CI/CD.
   * Alternatively, you can download the source code manually if you do not intend to use GitHub integration.

2. **Clone your fork locally.**

   * Clone your forked repository to your development machine.
   * If you prefer, you can use GitHub's integrated web-based code editor instead of cloning locally.

3. **Configure your environment variables.**

   * Complete every guide in the **[🛠️ Environment Setup Guides](#%EF%B8%8F-environment-setup-guides)** section to obtain all required API keys, database credentials, and other configuration values.
   * Populate your local `.env` file with the values from those guides.

4. **Save your environment variables.**

   * Once your `.env` file is complete, either:

     * Keep the `.env` file so it can be uploaded directly to Render, **or**
     * Save all environment variable names and values somewhere secure so you can enter them manually in the Render dashboard during deployment.

5. **Deploy to Render.**

   * Follow the **[Docs: Render Deployment Guide](./docs/render-deployment.md)** to connect your repository to Render, import the included `render.yaml` configuration, configure your environment variables, and complete the deployment.


## 🛠️ Environment Setup Guides

Before running the project, you'll need to configure a few external services. Each guide below walks you through creating an account, generating credentials, and wiring everything into your `.env` file.

- **[Docs: Groq Setup](./docs/groq-setup.md)** — Configures Groq, the project's primary **AI inference provider**. Groq analyzes discovered posts to determine whether they contain legitimate certification vouchers, discounts, promotions, or other relevant opportunities.

- **[Docs: Supabase Setup](./docs/supabase-setup.md)** — Configures a **Supabase PostgreSQL database** for the project, including creating a project, retrieving your database connection string, and connecting it via `DATABASE_URL`.

- **[Docs: Resend Setup](./docs/resend-setup.md)** — Configures **Resend** so the project can send email notifications, including generating an API key and setting up the required email environment variables.

- **[Docs: Gemini Setup](./docs/gemini-setup.md)** — Configures **Google Gemini** as the project's **fallback AI inference provider**, automatically used if Groq is unavailable, errors out, or cannot process a request.

- **[Docs: Reddit Setup](./docs/reddit-setup.md)** — Configures the **Reddit API** by creating an application, obtaining the required credentials, and setting the necessary environment variables so the project can discover and process certification-related posts.

> 💡 Complete these guides in order before moving on to running or testing the project.

## 📚 Additional Documentation

If you'd like to better understand the project's architecture, testing strategy, or contribute to its development, the following resources are available:

* **[Docs: Architecture](./docs/architecture.md)** — Provides a detailed overview of the system architecture, application components, data flow, and design decisions.

* **Testing** — The project's automated test suite is located in the [`tests`](./tests) directory. For information on running tests, writing new tests, and the project's testing strategy, refer to **[Docs: Testing](./docs/testing.md)**.

* **Contributing** — If you'd like to contribute to the project, please read **[CONTRIBUTING.md](./CONTRIBUTING.md)** for the project's contribution guidelines, development workflow, and best practices.

* **License** — The project's license is available in **[LICENSE](./LICENSE)**.

## Goals

* Reduce the time spent searching for certification discounts.
* Aggregate information from multiple trusted sources.
* Minimize false positives using AI-assisted filtering.
* Provide timely notifications for new certification opportunities.
* Offer an extensible platform that supports additional providers with minimal development effort.