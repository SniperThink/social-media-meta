flowchart TD
    A[upload_files_to_drive<br/>selected_media_paths, selected_caption, post_type] --> B[Get Google credentials]
    B --> C[Build Drive service]

    C --> D[create_social_media_root_folder]
    D --> E{Does 'Social Media Automation'<br/>folder exist?}
    E -->|Yes| F[Return existing folder ID]
    E -->|No| G[Create new folder<br/>'Social Media Automation']
    G --> H[Return new folder ID]

    F --> I[Generate timestamp]
    H --> I
    I --> J[Create post folder name<br/>post_type_timestamp or timestamp]
    J --> K[Create post folder in Drive<br/>under root folder]
    K --> L[Return post folder ID]

    L --> M[Initialize uploaded_media = []<br/>missing_media = []]

    M --> N[For each media_path in selected_media_paths]

    N --> O{Is media_path a URL?<br/>starts with http:// or https://}

    O -->|Yes| P[Download content from URL<br/>using requests.get()]
    P --> Q{Request successful?}
    Q -->|No| R[Log warning<br/>Add to missing_media<br/>Continue to next]
    R --> N

    Q -->|Yes| S[Extract file extension<br/>from URL or Content-Type header]
    S --> T[Determine MIME type<br/>image/* for images, video/mp4 for others]

    T --> U[Upload to R2 first<br/>using R2Client.put_object()]
    U --> V{R2 upload successful?}
    V -->|No| W[Log R2 failure<br/>r2_url = None]
    V -->|Yes| X[Generate R2 public URL<br/>r2_url = public URL]

    W --> Y[Use original content<br/>for Drive upload]
    X --> Z[Download content from R2 URL<br/>for Drive upload]
    Z --> AA{Drive download successful?}
    AA -->|No| BB[Log error<br/>Use original content as fallback]
    AA -->|Yes| CC[Use downloaded content<br/>from R2]

    Y --> DD[Create unique filename<br/>media_uuid.ext]
    BB --> DD
    CC --> DD

    DD --> EE[Create MediaIoBaseUpload<br/>from BytesIO(content)]
    EE --> FF[Upload to Drive<br/>with MIME type]
    FF --> GG[Add to uploaded_media<br/>with file_id, r2_url, etc.]
    GG --> HH[Log success]
    HH --> N

    O -->|No| II[Handle local file]
    II --> JJ[Resolve absolute path<br/>for temp dirs if needed]
    JJ --> KK{File exists?}
    KK -->|No| LL[Log warning<br/>Add to missing_media<br/>Continue to next]
    LL --> N

    KK -->|Yes| MM[Get filename and MIME type<br/>from file extension]
    MM --> NN[Upload to R2 first<br/>using upload_file_to_r2()]
    NN --> OO{R2 upload successful?}
    OO -->|No| PP[Log R2 failure<br/>r2_url = None]
    OO -->|Yes| QQ[Get R2 URL<br/>r2_url = info['url']]

    PP --> RR[Upload to Drive<br/>from local file]
    QQ --> SS[Download from R2 URL<br/>for Drive upload]
    SS --> TT{Drive download successful?}
    TT -->|No| UU[Log error<br/>Fallback to local file]
    TT -->|Yes| VV[Use R2 content<br/>for Drive upload]

    RR --> WW[Create MediaIoBaseUpload<br/>from file handle]
    UU --> WW
    VV --> WW

    WW --> XX[Upload to Drive<br/>with MIME type]
    XX --> YY[Add to uploaded_media<br/>with file_id, r2_url, etc.]
    YY --> ZZ[Log success]
    ZZ --> N

    N --> AAA{Any missing_media?}
    AAA -->|Yes| BBB[Log error<br/>Delete created Drive folder]
    BBB --> CCC[Raise Exception<br/>with missing files]

    AAA -->|No| DDD[Upload caption.txt<br/>to Drive folder]
    DDD --> EEE[Log caption upload success]

    EEE --> FFF[Log total uploads<br/>Return folder_id, uploaded_media]

    CCC --> GGG[End with error]
    FFF --> HHH[End with success]

    %% Styling
    classDef success fill:#d4edda,stroke:#155724
    classDef error fill:#f8d7da,stroke:#721c24
    classDef process fill:#cce5ff,stroke:#004085
    classDef decision fill:#fff3cd,stroke:#856404

    class A,B,C,I,J,M,HH,ZZ,DDD,EEE,FFF success
    class R,LL,BBB,CCC,GGG error
    class D,E,F,G,H,K,L,N,O,P,S,T,U,W,X,Y,Z,AA,BB,CC,DD,EE,FF,GG,II,JJ,KK,MM,NN,OO,PP,QQ,RR,SS,TT,UU,VV,WW,XX,YY,AAA process
    class Q,V,AA,TT,AAA,OO decision
