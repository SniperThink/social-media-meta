flowchart TD
    A[upload_files_to_drive<br/>selected_media_paths, selected_caption, post_type] --> B[get_google_creds<br/>from app/utils/auth.py]
    B --> C{Token exists<br/>and valid?}
    C -->|No| D[Refresh token<br/>or run OAuth flow]
    D --> E[Save new token<br/>to token.json]
    C -->|Yes| F[Build Drive service<br/>using googleapiclient]
    E --> F

    F --> G[create_social_media_root_folder]
    G --> H{Does 'Social Media Automation'<br/>folder exist in Drive?}
    H -->|Yes| I[Return existing folder ID]
    H -->|No| J[Create new folder<br/>'Social Media Automation']
    J --> K[Return new folder ID]

    I --> L[Generate timestamp<br/>YYYY-MM-DD_HH-MM-SS]
    K --> L
    L --> M[Create post folder name<br/>post_type_timestamp or timestamp]
    M --> N[Create post folder in Drive<br/>under root folder]
    N --> O[Return post folder ID]

    O --> P[Initialize uploaded_media = []<br/>missing_media = []]

    P --> Q[For each media_path in selected_media_paths]

    Q --> R{Is media_path a URL?<br/>starts with http:// or https://}

    R -->|Yes| S[Download content from URL<br/>using requests.get()]
    S --> T{Request successful?}
    T -->|No| U[Log warning<br/>Add to missing_media<br/>Continue to next]
    U --> Q

    T -->|Yes| V[Extract file extension<br/>from URL or Content-Type header]
    V --> W[Determine MIME type<br/>image/* for images, video/mp4 for others]

    W --> X[Upload to R2 first<br/>using R2Client.put_object()]
    X --> Y{R2 upload successful?}
    Y -->|No| Z[Log R2 failure<br/>r2_url = None]
    Y -->|Yes| AA[Generate R2 public URL<br/>using CLOUDFLARE_R2_PUBLIC_URL or default]

    Z --> BB[Use original content<br/>for Drive upload]
    AA --> CC[Download content from R2 URL<br/>for Drive upload]
    CC --> DD{Drive download successful?}
    DD -->|No| EE[Log error<br/>Use original content as fallback]
    DD -->|Yes| FF[Use downloaded content<br/>from R2]

    BB --> GG[Create unique filename<br/>media_uuid.ext]
    EE --> GG
    FF --> GG

    GG --> HH[Create MediaIoBaseUpload<br/>from BytesIO(content)]
    HH --> II[Upload to Drive<br/>with MIME type and folder ID]
    II --> JJ[Get uploaded file ID<br/>from Drive response]
    JJ --> KK[Add to uploaded_media<br/>with file_id, r2_url, file_name, mime_type]
    KK --> LL[Log success]
    LL --> Q

    R -->|No| MM[Handle local file]
    MM --> NN[Resolve absolute path<br/>for temp dirs if needed]
    NN --> OO{File exists?}
    OO -->|No| PP[Log warning<br/>Add to missing_media<br/>Continue to next]
    PP --> Q

    OO -->|Yes| QQ[Get filename and MIME type<br/>from file extension]
    QQ --> RR[Upload to R2 first<br/>using upload_file_to_r2()]
    RR --> SS{R2 upload successful?}
    SS -->|No| TT[Log R2 failure<br/>r2_url = None]
    SS -->|Yes| UU[Get R2 URL<br/>from r2_info['url']]

    TT --> VV[Upload to Drive<br/>from local file]
    UU --> WW[Download from R2 URL<br/>for Drive upload]
    WW --> XX{Drive download successful?}
    XX -->|No| YY[Log error<br/>Fallback to local file]
    XX -->|Yes| ZZ[Use R2 content<br/>for Drive upload]

    VV --> AAA[Create MediaIoBaseUpload<br/>from file handle]
    YY --> AAA
    ZZ --> AAA

    AAA --> BBB[Upload to Drive<br/>with MIME type and folder ID]
    BBB --> CCC[Get uploaded file ID<br/>from Drive response]
    CCC --> DDD[Add to uploaded_media<br/>with file_id, r2_url, file_name, mime_type]
    DDD --> EEE[Log success]
    EEE --> Q

    Q --> FFF{Any missing_media?}
    FFF -->|Yes| GGG[Log error<br/>Delete created Drive folder]
    GGG --> HHH[Raise Exception<br/>with missing files]

    FFF -->|No| III[Upload caption.txt<br/>to Drive folder using BytesIO]
    III --> JJJ[Log caption upload success]

    JJJ --> KKK[Log total uploads<br/>Return folder_id, uploaded_media]

    HHH --> LLL[End with error]
    KKK --> MMM[End with success]

    %% Related Services
    NNN[Database: crud.add_scheduled_post<br/>stores folder_id, event_id, uploaded_media]
    OOO[Calendar: google_calender.create_calendar_event<br/>creates event with Drive folder link]
    PPP[Cleanup: cleanup_service.check_and_delete_posts<br/>deletes old Drive folders after DELETE_DELAY_HOURS]
    QQQ[Publisher: publisher_service.get_media_bytes<br/>prefers R2 > Drive > HTTP for media access]
    RRR[Generator: generator_service uploads to R2<br/>returns R2 URLs for generated content]

    MMM --> NNN
    MMM --> OOO
    PPP -.-> GGG
    QQQ -.-> WW
    RRR -.-> RR

    %% Styling
    classDef success fill:#d4edda,stroke:#155724
    classDef error fill:#f8d7da,stroke:#721c24
    classDef process fill:#cce5ff,stroke:#004085
    classDef decision fill:#fff3cd,stroke:#856404
    classDef related fill:#e2e3e5,stroke:#6c757d

    class A,B,F,I,K,O,P,LL,EEE,JJJ,KKK,MMM success
    class U,PP,GGG,HHH,LLL error
    class D,E,G,H,J,L,M,N,Q,R,S,V,W,X,Z,AA,BB,CC,DD,EE,FF,GG,HH,II,JJ,KK,MM,NN,OO,QQ,RR,SS,TT,UU,VV,WW,XX,YY,ZZ,AAA,BBB,CCC,DDD,III,JJJ,FFF process
    class C,T,Y,DD,OO,XX,FFF decision
    class NNN,OOO,PPP,QQQ,RRR related
