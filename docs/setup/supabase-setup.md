# 🚀 Supabase Database Setup

This guide will help you create and configure a **Supabase PostgreSQL database** for this project. By the end of this guide, you will have:

- ✅ Created a Supabase account (or signed in)
- ✅ Created a new organization
- ✅ Created a new PostgreSQL project
- ✅ Retrieved your database connection string
- ✅ Configured the project's `.env` file to connect to your Supabase database

---

## 📋 Table of Contents

1. [Create a Supabase Account](#step-1-create-a-supabase-account)
2. [Sign Up or Sign In](#step-2-sign-up-or-sign-in)
3. [Create an Organization](#step-3-create-an-organization)
4. [Create a Project](#step-4-create-a-project)
5. [Retrieving the Database Connection String](#-retrieving-the-database-connection-string)
6. [Which Connection Type Should You Use?](#which-connection-type-should-you-use)
7. [Copy Your Connection String](#copy-your-connection-string)
8. [Passwords with Special Characters](#️-passwords-with-special-characters)
9. [Configure the Project](#-configure-the-project)
10. [Troubleshooting](#-troubleshooting)
11. [Setup Complete](#-setup-complete)

---

## Step 1: Create a Supabase Account

👉 [Go to Supabase](https://supabase.com/)

Click **Start your project**.

![Start your project](../images/supabase_1.png)

---

## Step 2: Sign Up or Sign In

You will automatically be redirected to:

👉 [Supabase Sign Up](https://supabase.com/dashboard/sign-up)

From here, either:

- Sign up for a new account
- Sign in if you already have one

Choose whichever option applies to you.

![Sign Up or Sign In](../images/supabase_2.png)

---

## Step 3: Create an Organization

After signing in, Supabase will prompt you to create your first organization.

Fill in the following fields:

- **Name** – Give your organization any name you like.
- **Type** – Select whichever option best describes you.
- **Plan** – Leave this as **Free** (default).

Once completed, click **Create Organization**.

![Create Organization](../images/supabase_3.png)

---

## Step 4: Create a Project

Next, Supabase will ask you to create a new project.

Fill out the project creation form as follows:

### 🏢 Organization

Leave this as the organization you just created (selected by default).

### 🔗 GitHub Integration

Connecting GitHub is **optional** and is **not required** for this project.

### 🏷️ Project Name

Choose any project name you prefer.

### 🔑 Database Password

Choose a **strong database password**.

> **❗ IMPORTANT**
>
> **You will need this password later when configuring your database connection string. Store it somewhere safe or make sure you remember it.**

### 🌍 Region

Choose whichever region is closest to you, or simply leave the default selection.

### 🔒 Security

Under **Security**, enable **only**:

- ✅ Enable Data API

Leave the following **unchecked**:

- ⬜ Automatically Expose New Tables
- ⬜ Enable Automatic RLS

This project does not require those options during initial setup.

Once everything is configured, click **Create Project**.

![Create Project](../images/supabase_4.png)

Wait a few moments while Supabase provisions your PostgreSQL database.

---

# 🔌 Retrieving the Database Connection String

Once your project has finished creating, you'll be taken to the Supabase dashboard.

At the top of the page, click **Connect**.

![Connect Button](../images/supabase_5.png)

A side panel will open.

Select **Direct** from the available connection methods.

You will now see three connection options.

---

## Which Connection Type Should You Use?

### 🔵 Session Pooler — Recommended

**Use Session Pooler.** It connects over IPv4 and works reliably across virtually all environments — home networks, offices, and most cloud providers.

---

### 🟢 Direct Connection

> **⚠️ Not recommended for most setups.**
>
> Direct Connection requires **IPv6 connectivity**, which many home networks and ISPs do not support. Even if it appears to work initially, it can fail intermittently depending on your network. Stick with Session Pooler unless you have a specific reason to use Direct Connection and have confirmed your environment supports IPv6.

---

### 🟡 Transaction Pooler

This is **not needed** for this project's use case.

Ignore this option.

![Connection Types](../images/supabase_6.png)

---

## Copy Your Connection String

Scroll down until you see the PostgreSQL connection string for whichever connection type you selected.

> **📝 Note:** The example below uses a **Direct Connection** string. Your string will look slightly different depending on your chosen connection type — the host and port will vary. Use whichever type you selected above; **Session Pooler is preferred** for most setups.

It will look similar to:

```text
postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxxx.supabase.co:5432/postgres
```

Copy the entire connection string.

Now replace:

```text
[YOUR-PASSWORD]
```

with the database password you created earlier.

> **⚡ Important — asyncpg Driver**
>
> This app runs on **FastAPI** with async database access, so it requires the **asyncpg** driver instead of the default psycopg2. After copying your connection string, change the scheme from `postgresql://` to `postgresql+asyncpg://`.
>
> ```text
> postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.xxxxxxxxx.supabase.co:5432/postgres
> ```

---

## ⚠️ Passwords with Special Characters

> **❗ IMPORTANT**
>
> **If your database password contains special characters, you MUST percent-encode those characters before placing the password into the connection string.**

For example, if your password is:

```text
MyP@ssw0rd!#
```

it becomes:

```text
MyP%40ssw0rd%21%23
```

Some common encodings are:

| Character | Encoded |
|-----------|----------|
| @ | %40 |
| : | %3A |
| / | %2F |
| ? | %3F |
| # | %23 |
| % | %25 |
| + | %2B |
| = | %3D |
| & | %26 |

Your final connection string should contain the **encoded** password.

![Connection String](../images/supabase_7.png)

---

# ⚙️ Configure the Project

Open your project's `.env` file.

Locate the following section:

```env
# Database URL.
# - Docker (docker compose up): leave this blank — compose sets it automatically.
# - Supabase: paste your connection string from the project settings (see docs/setup.md).
DATABASE_URL=""
```

Paste your completed connection string inside the quotes.

> **⚡ Remember the asyncpg driver:** Use `postgresql+asyncpg://` as the scheme, not plain `postgresql://`. The app uses FastAPI with async database access and requires asyncpg instead of the default psycopg2 driver.

Example:

```env
DATABASE_URL="postgresql+asyncpg://postgres:YourEncodedPassword@db.xxxxxxxxx.supabase.co:5432/postgres"
```

Save the file.

---

# 🛠️ Troubleshooting

## `getaddrinfo failed` on Startup

If the app fails to start with an error like this:

```
socket.gaierror: [Errno 11001] getaddrinfo failed
ERROR:    Application startup failed. Exiting.
```

This means the **Direct Connection** string is not reachable from your environment. Direct Connection uses IPv6, which many home networks and some ISPs do not support.

**Fix:** Switch to the **Session Pooler** connection string instead.

1. Go back to your Supabase dashboard and click **Connect**.
2. Select **Session Pooler** from the connection options.
3. Copy that connection string, apply your encoded password, and update `postgresql://` to `postgresql+asyncpg://` as before.
4. Paste it into your `.env` file and restart the app.

The Session Pooler connects over IPv4 and works on most home and office networks.

---

# 🎉 Setup Complete

Your project is now connected to your Supabase PostgreSQL database.

At this point, you can optionally configure additional Supabase features if desired, such as:

- Role-Based Access Control (RBAC)
- Row Level Security (RLS)
- Database Policies
- Authentication providers
- Storage buckets
- Edge Functions

These features are **not required** for this project and can be configured later if you are familiar with Supabase.