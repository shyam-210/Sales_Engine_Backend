# Sales Intelligence Engine

> AI-Powered Conversational Lead Qualification System with Real-time CRM Integration

[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688.svg?style=flat&logo=FastAPI)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?style=flat&logo=python)](https://www.python.org)
[![MongoDB](https://img.shields.io/badge/MongoDB-6.0+-green.svg?style=flat&logo=mongodb)](https://www.mongodb.com)
[![Groq](https://img.shields.io/badge/AI-Groq-orange.svg?style=flat)](https://groq.com)

---

## Live Demo

**Demo URL**: [Add your hosted demo link here]

**Dashboard Access**:
- URL: `/static/agent_widget.html`
- Password: `sales2025`

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Team](#team)

---

## Overview

The **Sales Intelligence Engine** is an autonomous AI-powered system that transforms website visitors into qualified leads through natural conversation. Built for **Zoho SalesIQ**, it combines advanced LLM analysis with real-time CRM integration to automate lead qualification and scoring.

### What It Does

- **Conversational AI**: Engages visitors in natural dialogue to understand their needs
- **Intent Detection**: Identifies buying intent, sentiment, and pain points
- **Smart Scoring**: Automatically scores leads 0-100 (Hot/Warm/Cold)
- **Auto CRM Sync**: Syncs qualified leads to Zoho CRM in real-time
- **Agent Dashboard**: Real-time dashboard for sales agents with AI insights
- **Session Tracking**: Tracks visitor sessions with 30-minute inactivity timeout

---

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Progressive Qualification** | Collects visitor info naturally through conversation (no forms!) |
| **AI Analysis** | ChatGPT OSS 120B analyzes intent, sentiment, urgency, and pain points |
| **Lead Scoring** | Automatic 0-100 scoring with Hot/Warm/Cold categorization |
| **CRM Integration** | Real-time sync to Zoho CRM with Lead ID tracking |
| **Session Management** | 30-minute session timeout with visit count tracking |
| **Agent Dashboard** | Password-protected dashboard with real-time lead updates |

### Intelligence Features

- **Intent Detection**: Buying, Support, or Browsing
- **Sentiment Analysis**: Positive, Neutral, or Frustrated
- **Budget Signals**: High, Low, or Null
- **Pain Point Extraction**: Identifies customer challenges
- **Competitor Detection**: Flags competitor mentions with battle cards
- **Recommended Actions**: Schedule Demo, Offer Discount, Escalate, or Nurture

---

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Visitor   │─────▶│  Zoho        │─────▶│   FastAPI   │
│  (Website)  │      │  SalesIQ     │      │   Backend   │
└─────────────┘      └──────────────┘      └──────┬──────┘
                                                   │
                     ┌─────────────────────────────┼─────────────┐
                     │                             │             │
                     ▼                             ▼             ▼
              ┌─────────────┐              ┌─────────────┐ ┌──────────┐
              │   Groq AI   │              │   MongoDB   │ │  Zoho    │
              │  (ChatGPT   │              │  (Sessions  │ │   CRM    │
              │  OSS 120B)  │              │  & Leads)   │ │          │
              └─────────────┘              └─────────────┘ └──────────┘
```

### Flow

1. **Visitor Engages** - Starts conversation via Zoho SalesIQ chatbot
2. **Intent Detection** - AI understands if they're asking about CRM/ERP/SalesIQ
3. **Natural Conversation** - Bot collects info through engaging dialogue
4. **AI Analysis** - ChatGPT OSS 120B scores intent, sentiment, urgency
5. **Auto Sync** - Lead appears in Zoho CRM and Agent Dashboard instantly

---

## Tech Stack

### Backend
- **Framework**: FastAPI 0.109.0
- **Language**: Python 3.11+
- **Server**: Uvicorn (ASGI)

### AI & Intelligence
- **LLM**: Groq (ChatGPT OSS 120B)
- **Analysis**: Intent, Sentiment, Pain Points, Competitor Detection

### Database
- **Primary**: MongoDB (Motor async driver)
- **Collections**: `visitor_sessions`, `leads`

### Integrations
- **Chat**: Zoho SalesIQ (webhook-based)
- **CRM**: Zoho CRM (OAuth 2.0)
- **HTTP Client**: httpx (async)

### Frontend
- **Dashboard**: HTML + Tailwind CSS + Vanilla JS
- **Home Page**: Responsive demo landing page

---

## Installation

### Prerequisites

- Python 3.11 or higher
- MongoDB (local or MongoDB Atlas)
- Zoho SalesIQ account
- Zoho CRM account
- Groq API key

### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/sales-intelligence-engine.git
cd sales-intelligence-engine
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Setup Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your credentials (see [Configuration](#configuration))

---

## Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
# Application
APP_NAME=Sales Intelligence Engine
APP_VERSION=2.0.0
DEBUG=false

# AI / LLM
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-70b-versatile

# Database
MONGO_URL=mongodb://localhost:27017
MONGO_DB_NAME=sales_intelligence

# Zoho CRM
ZOHO_CRM_CLIENT_ID=your_client_id
ZOHO_CRM_CLIENT_SECRET=your_client_secret
ZOHO_CRM_REFRESH_TOKEN=your_refresh_token
ZOHO_CRM_API_URL=https://www.zohoapis.in

# Zoho SalesIQ
ZOHO_SECRET=your_salesiq_secret
```

### Getting API Keys

#### Groq API Key
1. Visit [console.groq.com](https://console.groq.com)
2. Create account and generate API key

#### Zoho CRM OAuth
1. Run setup script: `python setup_zoho_oauth.py`
2. Follow OAuth flow to get refresh token

#### Zoho SalesIQ
1. Login to Zoho SalesIQ
2. Go to Settings → Developers → Secret Key
3. Copy the secret key

---

## Usage

### Running Locally

```bash
# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/api/docs
- **Home Page**: http://localhost:8000/static/index.html
- **Dashboard**: http://localhost:8000/static/agent_widget.html

### Dashboard Access

- **URL**: `/static/agent_widget.html`
- **Password**: `sales2025` (configurable)

### Testing the Chatbot

1. Open the home page: http://localhost:8000/static/index.html
2. Chat with the bot in the bottom-right widget
3. Try queries like:
   - "I need a CRM for my team"
   - "Looking for ERP solutions"
   - "Tell me about SalesIQ"

---

## API Documentation

### Interactive API Docs

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

### Key Endpoints

#### Health Check
```http
GET /
GET /health
```

#### Intelligence API
```http
POST /api/v1/chat
POST /api/v1/qualify
GET  /api/v1/leads/top
GET  /api/v1/leads/{visitor_id}
```

### Authentication

All API endpoints require the `x-salesiq-auth` header:

```http
x-salesiq-auth: your_zoho_secret
```

---

## Project Structure

```
Sales_Engine_Backend/
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py              # Configuration settings
│   ├── models/
│   │   ├── __init__.py
│   │   ├── lead.py                # Lead & scoring models
│   │   └── session.py             # Session tracking models
│   ├── routers/
│   │   ├── __init__.py
│   │   └── intelligence.py        # Main API routes
│   ├── services/
│   │   ├── __init__.py
│   │   ├── conversation_manager.py # Chat flow logic
│   │   ├── crm_service.py         # Zoho CRM integration
│   │   ├── extractor_service.py   # Data extraction
│   │   ├── groq_service.py        # AI/LLM service
│   │   ├── session_manager.py     # Session management
│   │   └── zoho_token_manager.py  # OAuth token refresh
│   ├── static/
│   │   ├── index.html             # Landing page
│   │   └── agent_widget.html      # Agent dashboard
│   ├── __init__.py
│   └── main.py                    # FastAPI app entry point
├── .env                           # Environment variables (not in git)
├── .env.example                   # Example environment file
├── .gitignore                     # Git ignore rules
├── README.md                      # This file
├── requirements.txt               # Python dependencies
├── clear_db.py                    # Database cleanup utility
├── setup_zoho_oauth.py            # Zoho OAuth setup
└── zobot_handler.deluge           # SalesIQ bot handler code
```

---


## Team

**Team Defaulters**

### Shyam
- **Email**: [shyamjk10@gmail.com](mailto:shyamjk10@gmail.com)
- **GitHub**: [Add GitHub Link]
- **LeetCode**: [Add LeetCode Profile Link]
- **Portfolio**: [Add Portfolio Link]

### Madhan
- **Email**: [maddymadhan9310@gmail.com](mailto:maddymadhan9310@gmail.com)
- **GitHub**: [Add GitHub Link]
- **LeetCode**: [Add LeetCode Profile Link]
- **Portfolio**: [Add Portfolio Link]

---


