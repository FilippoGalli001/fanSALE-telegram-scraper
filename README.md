# Ticket Availability Telegram Bot

This Telegram bot monitors ticket availability for events on ticket sale websites (fanSALE and TicketOne) and notifies users when tickets become available for their selected events. Users can search for events by artist name, track specific concerts, and receive notifications when new tickets are found.

## Features

- **Search Events**: Users can search for events by artist name.
- **Track Concerts**: Users can select concerts to track ticket availability.
- **Notifications**: The bot checks for new tickets every 30 minutes and notifies users.
- **Manage Trackers**: Users can view and remove their active trackers (up to 2 active trackers per user).
- **Concurrent Requests**: Supports multiple users making requests simultaneously without blocking.

## Architecture
The project consists of two main components:

- **Telegram Bot**: Handles user interactions, manages trackers, and communicates with the scraper microservice.
- **Scraper Microservice**: Performs web scraping tasks to fetch event and ticket information.

  
