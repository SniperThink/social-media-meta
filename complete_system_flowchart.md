```mermaid
graph TD
    subgraph User Interaction (Frontend)
        A[User opens Frontend] --> B{Selects Post Type};
        B --> C[Enters Prompt];
        C --> D[Clicks "Generate"];
    end

    subgraph Content Generation (API)
        D --> E[POST /api/content/generate];
        E --> F[generator_service];
        F --> G[Google Gemini AI];
        G --> H[Generated Content (Media URLs, Captions)];
        H --> I[User reviews and modifies content];
        I --> J[Clicks "Schedule"];
    end

    subgraph Scheduling (API)
        J --> K[POST /api/schedule/];
        K --> L[schedular_service];
        L --> M[google_drive.upload_files_to_drive];
        L --> N[google_calender.create_calendar_event];
        L --> O[crud.add_scheduled_post];
        M --> P[Google Drive];
        N --> Q[Google Calendar];
        O --> R[Database];
    end

    subgraph Background Processing
        S[APScheduler] --> T{Every minute};
        T --> U[cleanup_service.check_and_trigger_posts];
        U --> V{Finds due posts};
        V --> W[POST /api/webhook/schedule];
    end

    subgraph Publishing (Webhook)
        W --> X[webhook_service];
        X --> Y{Retrieve Media};
        Y -- R2 --> Z[Cloudflare R2];
        Y -- Drive --> AA[Google Drive];
        Y -- HTTP --> BB[Direct Download];
        X --> CC[Validate & Prepare Media];
        CC --> DD[Upload to R2];
        DD --> EE[Cloudflare R2];
        X --> FF[Send to External Webhook];
        FF --> GG[Make.com];
        GG --> HH[Social Media Platform (e.g., Instagram)];
        X --> II[Update Database];
        II --> R;
    end

    style User Interaction fill:#f9f,stroke:#333,stroke-width:2px
    style Content Generation fill:#ccf,stroke:#333,stroke-width:2px
    style Scheduling fill:#cfc,stroke:#333,stroke-width:2px
    style Background Processing fill:#ffc,stroke:#333,stroke-width:2px
    style Publishing fill:#fcc,stroke:#333,stroke-width:2px
```