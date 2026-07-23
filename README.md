<div align="center">

# 🎟️ VoucherBot

**An intelligent certification voucher aggregator**

*Continuously monitors community and official sources for certification discounts, free exam opportunities, beta exams, and promotional campaigns.*

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-see%20LICENSE-lightgrey)
![Deploy](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render&logoColor=white)
![Status](https://img.shields.io/badge/status-active-success)

</div>

---

## 📖 Table of Contents

- [Overview](#overview)
- [🚀 Deployment](#-deployment)
- [🛠️ Environment Setup Guides](#%EF%B8%8F-environment-setup-guides)
- [📚 Additional Documentation](#-additional-documentation)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)
- [🎯 Goals](#-goals)

---

## Overview

VoucherBot is a Python application that automates the discovery of certification offers across the internet. Instead of manually checking dozens of websites, blogs, forums, and communities, VoucherBot continuously monitors multiple sources, filters relevant content, and identifies potential certification promotions using **keyword scoring** and **AI-powered analysis**.

The project is designed to be **modular**, making it easy to add new data sources and notification channels over time.

---

## 🚀 Deployment

Follow the steps below to deploy the project.

| Step | Action |
|------|--------|
| **1** | **Fork or download the repository.** Forking is the recommended approach, since the project includes a `Dockerfile` and a `render.yaml` file — Render can use either of these to build and run the application, and GitHub integration makes future updates significantly easier through automatic CI/CD. Alternatively, download the source code manually if you don't intend to use GitHub integration. |
| **2** | **Clone your fork locally** *(optional)*. This step isn't strictly necessary unless you want to modify the code itself. For a standard Render deployment, you only need to download `.env.example` from the repository, rename it to `.env`, and populate it with your own values — no local clone required. If you do want to work with the code, clone your forked repository to your development machine, or use GitHub's integrated web-based code editor instead of cloning locally. |
| **3** | **Configure your environment variables.** Complete every guide in the [🛠️ Environment Setup Guides](#%EF%B8%8F-environment-setup-guides) section below to obtain all required API keys, database credentials, and other configuration values. Populate your local `.env` file with the values from those guides. |
| **4** | **Save your environment variables.** Once your `.env` file is complete, either keep it so it can be uploaded directly to Render, **or** save all environment variable names and values somewhere secure to enter manually in the Render dashboard during deployment. |
| **5** | **Deploy to Render.** Head to the [🚀 Deployment Guides](#-deployment-guides) section below and follow the guides there to connect your repository to Render, configure your environment variables, and complete the deployment. |

> 💡 **Tip:** Steps 3–4 go faster if you open each setup guide in its own browser tab before you start.

🎉 **Voilà!** Your app is now up and running. VoucherBot will continuously monitor your configured sources in the background and automatically deliver any certification vouchers it finds straight to your email — no manual checking required.

---

## 🛠️ Environment Setup Guides

Before running the project, you'll need to configure a few external services. Each guide below walks you through creating an account, generating credentials, and wiring everything into your `.env` file.

| Service | Role | Guide |
|---------|------|-------|
| 🧠 **Groq** | Primary **AI inference provider** — analyzes discovered posts to determine whether they contain legitimate certification vouchers, discounts, promotions, or other relevant opportunities. | [Groq Setup](./docs/setup/groq-setup.md) |
| 🗄️ **Supabase** | **PostgreSQL database** for the project — includes creating a project, retrieving your database connection string, and connecting it via `DATABASE_URL`. | [Supabase Setup](./docs/setup/supabase-setup.md) |
| ✉️ **Resend** | Sends **email notifications** — includes generating an API key and setting up the required email environment variables. | [Resend Setup](./docs/setup/resend-setup.md) |
| 🤖 **Google Gemini** | **Fallback AI inference provider**, automatically used if Groq is unavailable, errors out, or cannot process a request. | [Gemini Setup](./docs/setup/gemini-setup.md) |
| 👽 **Reddit API** | Enables the project to **discover and process** certification-related posts — includes creating an application and obtaining the required credentials. | [Reddit Setup](./docs/setup/reddit-setup.md) |

> ⚠️ **Complete these guides** before moving on to running or testing the project.

### 🚀 Deployment Guides

These guides cover getting your app running in the cloud and keeping it alive. They are separate from environment setup — complete the environment guides above first.

| Guide | Description |
|-------|-------------|
| 🚀 [Render Deployment](./docs/setup/render-deployment.md) | Deploy the application to Render — covers connecting your repository, configuring environment variables, and completing the deployment. |
| ⏱️ [UptimeRobot Setup](./docs/setup/uptime-bot-setup.md) *(optional)* | Prevent your Render free tier service from spinning down by setting up a monitor that periodically pings your app. |

---

## 📚 Additional Documentation

| Resource | Description |
|----------|-------------|
| 🏗️ [Architecture](./docs/details/architecture.md) | A detailed overview of the system architecture, application components, data flow, and design decisions. |
| 📋 [Detailed Summary](./docs/details/detailed-summary.md) | A highly detailed summary of the entire project. |
| ⚙️ [Configuration](./docs/details/configuration.md) | A full reference of all available configurations. |
| 🗂️ [Schema](./docs/details/schema.md) | The project's data schema. |
| ℹ️ [Project Info](./docs/details/project-info.md) | General information about the project. |
| 🧪 [Testing](./docs/details/testing.md) | How to run the automated test suite, what to expect while testing, and simple troubleshooting steps. |
| 📰 [Sources](./sources/source.md) | An overview of all the sources used by the project. |

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](./CONTRIBUTING.md) for contribution guidelines, development workflow, and best practices before submitting a pull request.

---

## 📄 License

This project is licensed under the terms described in [LICENSE](./LICENSE).

---

## 🎯 Goals

- ⏱️ **Reduce the time** spent searching for certification discounts.
- 🌐 **Aggregate information** from multiple trusted sources.
- 🎯 **Minimize false positives** using AI-assisted filtering.
- 🔔 **Provide timely notifications** for new certification opportunities.
- 🧩 **Offer an extensible platform** that supports additional providers with minimal development effort.