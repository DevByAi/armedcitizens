# Overview

This is a Telegram bot application that manages a community verification and marketplace system. The bot handles user verification, admin approval workflows, and selling post management across multiple Telegram group chats. Users must go through a verification process (providing name, phone, and license photo) before gaining access to community groups. Approved users can create selling posts that require admin approval before being published to the community.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Application Type
Python-based Telegram bot using webhooks for asynchronous message handling.

## Backend Architecture

**Framework**: python-telegram-bot library (v20.8)
- **Rationale**: Provides comprehensive async/await support for handling Telegram's Bot API
- **Pattern**: Handler-based architecture with separate modules for verification, admin, and selling functionality
- **Deployment**: Webhook mode for production (vs polling), using Flask for webhook endpoint

**Database ORM**: SQLAlchemy 2.0
- **Rationale**: Provides robust ORM capabilities with session management
- **Pattern**: Session-per-operation using context managers (`get_db_session()`)
- **Models**: Two primary entities - `User` and `SellPost`

## Data Models

**User Model**:
- Tracks Telegram users with verification status (`is_approved`, `is_banned`)
- Stores verification data (full_name, phone_number, license_photo_id)
- Admin role management (`is_admin`)

**SellPost Model**:
- User-generated selling posts requiring admin approval
- Tracks approval status and active state
- Records last sent date for broadcast management

## Access Control & Permissions

**Multi-tier Permission System**:
- **Super Admin**: Single root administrator (configured via `SUPER_ADMIN_ID`)
- **Regular Admins**: Can approve users and manage posts
- **Approved Users**: Verified users with community access
- **Pending Users**: New members with restricted permissions until verified

**Permission Management**:
- New members are automatically restricted from sending messages
- Permissions granted across all community chats after approval
- Bot manages ChatPermissions via Telegram's API

## Handler Architecture

**Modular Handler System**:
- `handlers/verification.py`: New member onboarding and verification flow
- `handlers/admin.py`: Admin commands for user approval and management
- `handlers/selling.py`: Marketplace post creation and approval workflow
- `handlers/utils.py`: Shared utilities for permission management

**Conversation Flow**:
- Uses ConversationHandler for multi-step verification process
- States: AWAITING_NAME → AWAITING_PHONE → AWAITING_LICENSE
- Context-based state management via `context.user_data`

## Message Processing

**System Message Cleanup**:
- Automatically deletes join/leave messages to reduce clutter
- Requires appropriate bot permissions in group chats

**Post Approval Workflow**:
1. User creates post via `/sell` command
2. Post saved to database with `is_approved_by_admin=False`
3. Admins review and approve
4. Approved posts broadcast to community chats

# External Dependencies

## Telegram Bot API
- Primary interface for all bot operations
- Webhook-based message reception
- Required bot permissions: manage members, delete messages, restrict users

## Database
- **Type**: PostgreSQL (via psycopg2-binary driver)
- **Connection**: SQLAlchemy ORM with connection string from `DATABASE_URL` or `DB_URL` environment variable
- **Schema**: Automatically created via `Base.metadata.create_all()`

## Environment Configuration

**Required Variables**:
- `BOT_TOKEN`: Telegram bot authentication token
- `DATABASE_URL` or `DB_URL`: PostgreSQL connection string
- `ALL_COMMUNITY_CHATS`: Comma-separated chat IDs for community groups
- `ADMIN_CHAT_ID`: Channel for admin notifications and verification requests
- `SUPER_ADMIN_ID`: Telegram user ID of the super administrator
- `WEBHOOK_URL`: Public URL for webhook endpoint
- `PORT`: Server port (default: 5000)

## Deployment Stack
- **Web Server**: Gunicorn WSGI server
- **Web Framework**: Flask with async support
- **Timezone Handling**: pytz library for datetime operations

## Third-party Libraries
- `python-telegram-bot[webhooks]`: Core bot framework with webhook support
- `SQLAlchemy`: Database ORM
- `python-dotenv`: Environment variable management
- `asgiref`: ASGI utilities for async support