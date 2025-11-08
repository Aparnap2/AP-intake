# SECURITY REMEDIATION IMPLEMENTATION GUIDE
**AP Intake & Validation System**
Step-by-Step Security Vulnerability Fixes

---

## 🚨 CRITICAL VULNERABILITIES - IMMEDIATE FIXES

### 1. Implement Authentication System (CRITICAL)

#### Step 1: Update Authentication Dependencies
```bash
# Add required security packages
uv add "python-jose[cryptography]" "passlib[bcrypt]" "python-multipart"
```

#### Step 2: Create User Model
```python
# app/models/user.py
from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
import enum

class UserRole(enum.Enum):
    ADMIN = "admin"
    ACCOUNTANT = "accountant"
    VIEWER = "viewer"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(Enum(UserRole), default=UserRole.VIEWER)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
```

#### Step 3: Implement Authentication Service
```python
# app/services/auth_service.py
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[str]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username: str = payload.get("sub")
            if username is None:
                return None
            return username
        except JWTError:
            return None

    async def authenticate_user(self, db: AsyncSession, username: str, password: str) -> Optional[User]:
        result = await db.execute(
            select(User).where((User.username == username) | (User.email == username))
        )
        user = result.scalar_one_or_none()
        if not user or not self.verify_password(password, user.hashed_password):
            return None
        return user

auth_service = AuthService()
```

#### Step 4: Update Authentication Dependencies
```python
# app/api/api_v1/deps.py (REVISED)
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import auth_service

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        username = auth_service.verify_token(credentials.credentials)
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def require_role(required_role: str):
    """Decorator to require specific user role."""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role.value != required_role and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker
```

#### Step 5: Add Authentication Endpoints
```python
# app/api/api_v1/endpoints/auth.py
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import Token, UserCreate, UserResponse
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import auth_service

router = APIRouter()

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return access token."""
    user = await auth_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=UserResponse)
async def register_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user."""
    # Check if user exists
    result = await db.execute(
        select(User).where((User.username == user.username) | (User.email == user.email))
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username or email already registered"
        )

    # Create new user
    hashed_password = auth_service.get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password,
        role=user.role,
    )

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    return db_user
```

### 2. Fix SQL Injection Vulnerabilities (CRITICAL)

#### Step 1: Audit and Fix Database Queries
```python
# ❌ VULNERABLE - DON'T USE
query = f"SELECT * FROM invoices WHERE vendor_id = '{vendor_id}'"
result = db.execute(query)

# ✅ SECURE - USE PARAMETERIZED QUERIES
from sqlalchemy import select, text

# Using SQLAlchemy ORM
query = select(Invoice).where(Invoice.vendor_id == vendor_id)
result = await db.execute(query)

# Using raw SQL with parameters
query = text("SELECT * FROM invoices WHERE vendor_id = :vendor_id")
result = await db.execute(query, {"vendor_id": vendor_id})
```

#### Step 2: Secure Invoice Repository
```python
# app/repositories/invoice_repository.py
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from uuid import UUID

from app.models.invoice import Invoice, InvoiceStatus

class InvoiceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_invoice_by_id(self, invoice_id: UUID) -> Optional[Invoice]:
        """Get invoice by ID safely."""
        result = await self.db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        )
        return result.scalar_one_or_none()

    async def get_invoices_by_vendor(self, vendor_id: UUID) -> List[Invoice]:
        """Get invoices by vendor ID safely."""
        result = await self.db.execute(
            select(Invoice).where(Invoice.vendor_id == vendor_id)
        )
        return result.scalars().all()

    async def search_invoices(self, search_term: str, limit: int = 100) -> List[Invoice]:
        """Search invoices safely with parameterized queries."""
        search_pattern = f"%{search_term}%"
        result = await self.db.execute(
            select(Invoice).where(
                or_(
                    Invoice.file_name.ilike(search_pattern),
                    Invoice.file_hash.ilike(search_pattern)
                )
            ).limit(limit)
        )
        return result.scalars().all()

    async def get_invoices_with_filters(
        self,
        status: Optional[str] = None,
        vendor_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Invoice], int]:
        """Get invoices with filters safely."""
        query = select(Invoice)
        conditions = []

        if status:
            try:
                status_enum = InvoiceStatus[status.upper()]
                conditions.append(Invoice.status == status_enum)
            except KeyError:
                raise ValueError(f"Invalid status: {status}")

        if vendor_id:
            conditions.append(Invoice.vendor_id == vendor_id)

        if conditions:
            query = query.where(and_(*conditions))

        # Get total count
        count_query = select(func.count(Invoice.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))

        count_result = await self.db.execute(count_query)
        total = count_result.scalar()

        # Apply pagination
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        invoices = result.scalars().all()

        return invoices, total
```

#### Step 3: Secure API Endpoints
```python
# app/api/api_v1/endpoints/invoices.py (SECURE VERSION)
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.api_v1.deps import get_current_active_user
from app.db.session import get_db
from app.models.invoice import Invoice
from app.models.user import User
from app.repositories.invoice_repository import InvoiceRepository

router = APIRouter()

@router.get("/")
async def list_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    vendor_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List invoices with secure filtering."""
    try:
        repo = InvoiceRepository(db)

        # Parse and validate vendor_id
        vendor_uuid = None
        if vendor_id:
            try:
                vendor_uuid = UUID(vendor_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid vendor_id format")

        # Get invoices safely
        invoices, total = await repo.get_invoices_with_filters(
            status=status,
            vendor_id=vendor_uuid,
            skip=skip,
            limit=limit
        )

        return {
            "invoices": invoices,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## ⚠️ HIGH SEVERITY VULNERABILITIES - PRIORITY FIXES

### 3. Secure File Upload System (HIGH)

#### Step 1: Implement Secure File Upload Service
```python
# app/services/secure_upload_service.py
import os
import hashlib
import magic
from typing import Dict, List, Optional
from pathlib import Path
from fastapi import UploadFile, HTTPException
from PIL import Image
import fitz  # PyMuPDF for PDF validation
import tempfile

from app.core.config import settings

class SecureUploadService:
    def __init__(self):
        self.allowed_mime_types = {
            'application/pdf': ['.pdf'],
            'image/jpeg': ['.jpg', '.jpeg'],
            'image/png': ['.png'],
        }
        self.max_file_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        self.upload_path = Path(settings.STORAGE_PATH)
        self.upload_path.mkdir(parents=True, exist_ok=True)

    def validate_file_type(self, file: UploadFile) -> bool:
        """Validate file type using magic bytes."""
        # Read first few bytes to determine real file type
        file_content = file.file.read(1024)
        file.file.seek(0)  # Reset file pointer

        # Use python-magic to detect real file type
        mime_type = magic.from_buffer(file_content, mime=True)

        # Check if detected MIME type is allowed
        if mime_type not in self.allowed_mime_types:
            raise HTTPException(
                status_code=400,
                detail=f"File type {mime_type} not allowed"
            )

        # Check file extension matches detected type
        allowed_extensions = self.allowed_mime_types[mime_type]
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File extension {file_extension} not allowed for {mime_type}"
            )

        return True

    def validate_pdf_content(self, file_content: bytes) -> bool:
        """Validate PDF content to prevent malicious PDFs."""
        try:
            # Use PyMuPDF to validate PDF
            doc = fitz.open(stream=file_content, filetype="pdf")

            # Check PDF is not password protected
            if doc.needs_pass:
                raise HTTPException(
                    status_code=400,
                    detail="Password-protected PDFs are not allowed"
                )

            # Check PDF page count
            if len(doc) > 50:  # Max 50 pages
                raise HTTPException(
                    status_code=400,
                    detail="PDF exceeds maximum page limit of 50"
                )

            # Check for suspicious content
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()

                # Check for suspicious JavaScript
                if "javascript:" in text.lower():
                    raise HTTPException(
                        status_code=400,
                        detail="PDF contains suspicious JavaScript content"
                    )

            doc.close()
            return True

        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=400,
                detail="Invalid or corrupted PDF file"
            )

    def validate_image_content(self, file_content: bytes, mime_type: str) -> bool:
        """Validate image content to prevent malicious images."""
        try:
            # Use PIL to validate image
            with Image.open(io.BytesIO(file_content)) as img:
                # Check image dimensions
                if img.size[0] > 10000 or img.size[1] > 10000:
                    raise HTTPException(
                        status_code=400,
                        detail="Image dimensions exceed maximum allowed size"
                    )

                # Check for EXIF data in images (can be malicious)
                if hasattr(img, '_getexif') and img._getexif():
                    # Optionally strip EXIF data
                    pass

                # Convert to RGB if necessary (prevents some palette-based attacks)
                if img.mode not in ['RGB', 'L']:
                    img = img.convert('RGB')

                # Save validated image to buffer
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG' if mime_type == 'image/jpeg' else 'PNG')
                return buffer.getvalue()

        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=400,
                detail="Invalid or corrupted image file"
            )

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and injection."""
        # Remove path components
        filename = os.path.basename(filename)

        # Remove dangerous characters
        dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')

        # Limit filename length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255-len(ext)] + ext

        # Ensure filename is not empty
        if not filename or filename.startswith('.'):
            filename = f"upload_{int(time.time())}{os.path.splitext(filename)[1]}"

        return filename

    async def secure_upload(self, file: UploadFile) -> Dict[str, str]:
        """Securely upload and validate file."""
        # File size validation
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        if file_size > self.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"File size {file_size} exceeds maximum {self.max_file_size}"
            )

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file not allowed")

        # Validate file type
        self.validate_file_type(file)

        # Read file content
        file_content = await file.read()

        # Detect MIME type
        mime_type = magic.from_buffer(file_content, mime=True)

        # Content-specific validation
        if mime_type == 'application/pdf':
            validated_content = self.validate_pdf_content(file_content)
        elif mime_type in ['image/jpeg', 'image/png']:
            validated_content = self.validate_image_content(file_content, mime_type)
        else:
            validated_content = file_content

        # Calculate file hash
        file_hash = hashlib.sha256(validated_content).hexdigest()

        # Check for duplicates
        existing_file = self.upload_path / f"{file_hash}.bin"
        if existing_file.exists():
            return {
                "filename": file.filename,
                "file_path": str(existing_file),
                "file_hash": file_hash,
                "file_size": len(validated_content),
                "mime_type": mime_type,
                "is_duplicate": True
            }

        # Sanitize filename
        safe_filename = self.sanitize_filename(file.filename)

        # Generate unique filename
        timestamp = int(time.time())
        stored_filename = f"{timestamp}_{file_hash[:8]}_{safe_filename}"
        file_path = self.upload_path / stored_filename

        # Write file securely
        with open(file_path, 'wb') as f:
            f.write(validated_content)

        # Set secure permissions
        os.chmod(file_path, 0o644)

        return {
            "filename": safe_filename,
            "file_path": str(file_path),
            "file_hash": file_hash,
            "file_size": len(validated_content),
            "mime_type": mime_type,
            "is_duplicate": False
        }

secure_upload_service = SecureUploadService()
```

#### Step 2: Update Invoice Upload Endpoint
```python
# app/api/api_v1/endpoints/invoices.py (SECURE UPLOAD)
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_v1.deps import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.services.secure_upload_service import secure_upload_service

@router.post("/upload")
async def upload_invoice(
    file: UploadFile,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Securely upload and process an invoice file."""
    try:
        # Secure file upload
        upload_result = await secure_upload_service.secure_upload(file)

        # Create invoice record
        invoice = Invoice(
            vendor_id=None,  # Will be determined from extraction
            file_url=upload_result["file_path"],
            file_hash=upload_result["file_hash"],
            file_name=upload_result["filename"],
            file_size=f"{upload_result['file_size'] / (1024*1024):.1f}MB",
            mime_type=upload_result["mime_type"],
            status=InvoiceStatus.RECEIVED,
            workflow_state="uploaded",
            uploaded_by=current_user.id,
        )

        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)

        # Queue processing task
        if not upload_result["is_duplicate"]:
            process_invoice_task.delay(
                str(invoice.id),
                upload_result["file_path"],
                upload_result["file_hash"]
            )

        return {
            "message": "File uploaded successfully",
            "invoice_id": invoice.id,
            "is_duplicate": upload_result["is_duplicate"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")
```

### 4. Fix CORS Configuration (HIGH)

#### Step 1: Secure CORS Configuration
```python
# app/core/config.py (UPDATED CORS SETTINGS)
class Settings(BaseSettings):
    # ... other settings ...

    # Secure CORS configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",  # Development frontend
        "https://yourdomain.com",  # Production frontend
        "https://staging.yourdomain.com",  # Staging environment
    ]

    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: List[str] = [
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-API-Key",
    ]

    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
```

#### Step 2: Update Main Application
```python
# app/main.py (SECURE CORS)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Remove wildcard CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "yourdomain.com", "*.yourdomain.com"]
)
```

### 5. Add Security Headers (HIGH)

#### Step 1: Implement Security Headers Middleware
```python
# app/middleware/security_headers.py
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "  # Remove unsafe-inline in production
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp

        # HSTS (HTTPS only in production)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # Remove server information
        if "Server" in response.headers:
            del response.headers["Server"]
        if "X-Powered-By" in response.headers:
            del response.headers["X-Powered-By"]

        return response

# Add to main application
app.add_middleware(SecurityHeadersMiddleware)
```

---

## ⚡ MEDIUM SEVERITY VULNERABILITIES - STANDARD FIXES

### 6. Implement Rate Limiting (MEDIUM)

#### Step 1: Add Rate Limiting Dependencies
```bash
uv add "slowapi" "redis"
```

#### Step 2: Implement Rate Limiting
```python
# app/middleware/rate_limiting.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import redis

# Initialize Redis for rate limiting
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379"
)

# Rate limit exceeded handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."}
    )

# Apply rate limiting to endpoints
@router.post("/upload")
@limiter.limit("10/minute")  # 10 uploads per minute per IP
async def upload_invoice(
    request: Request,
    file: UploadFile,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # ... upload logic ...
```

### 7. Implement Input Validation (MEDIUM)

#### Step 1: Create Validation Schemas
```python
# app/api/schemas/validation.py
from pydantic import BaseModel, validator, EmailStr
from typing import Optional
from uuid import UUID
import re

class InvoiceSearchRequest(BaseModel):
    search_term: Optional[str] = None
    vendor_id: Optional[UUID] = None
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 100
    offset: int = 0

    @validator('search_term')
    def validate_search_term(cls, v):
        if v:
            # Prevent injection attacks
            if len(v) > 100:
                raise ValueError('Search term too long')
            # Remove dangerous characters
            dangerous_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '--']
            for char in dangerous_chars:
                v = v.replace(char, '')
        return v

    @validator('limit')
    def validate_limit(cls, v):
        if v < 1 or v > 1000:
            raise ValueError('Limit must be between 1 and 1000')
        return v

    @validator('offset')
    def validate_offset(cls, v):
        if v < 0:
            raise ValueError('Offset must be non-negative')
        return v

class UserRegistrationRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3 or len(v) > 50:
            raise ValueError('Username must be between 3 and 50 characters')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        return v
```

### 8. Error Message Sanitization (MEDIUM)

#### Step 1: Secure Error Handling
```python
# app/core/exceptions.py
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)

class APIntakeException(Exception):
    """Custom application exception."""
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}
        super().__init__(self.message)

class SecurityException(APIntakeException):
    """Security-related exception."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "SECURITY_ERROR", details)

# Exception handlers
async def ap_intake_exception_handler(request: Request, exc: APIntakeException):
    """Handle custom application exceptions."""
    logger.error(f"AP Intake Exception: {exc.message}", exc_info=True)

    return JSONResponse(
        status_code=400,
        content={
            "error": exc.error_code,
            "message": exc.message,
            # Include details only in development
            "details": exc.details if settings.DEBUG else None
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation exceptions."""
    logger.warning(f"Validation error: {exc.errors()}")

    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid input data",
            "details": exc.errors() if settings.DEBUG else "Please check your input"
        }
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    # Don't expose internal error details
    if exc.status_code >= 500:
        logger.error(f"Internal server error: {exc.detail}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred"
            }
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": f"HTTP_{exc.status_code}",
            "message": exc.detail
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred"
        }
    )
```

---

## 🔒 SECURITY TESTING IMPLEMENTATION

### 9. Automated Security Testing (LOW/MEDIUM)

#### Step 1: Add Security Testing to CI/CD
```yaml
# .github/workflows/security.yml
name: Security Testing

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  security-scan:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install bandit safety semgrep

    - name: Run Bandit Security Scanner
      run: bandit -r app/ -f json -o bandit-report.json

    - name: Run Safety Dependency Check
      run: safety check --json --output safety-report.json

    - name: Run Semgrep Security Scan
      run: semgrep --config=auto app/ --json --output semgrep-report.json

    - name: Upload Security Reports
      uses: actions/upload-artifact@v3
      with:
        name: security-reports
        path: |
          bandit-report.json
          safety-report.json
          semgrep-report.json
```

#### Step 2: Security Unit Tests
```python
# tests/security/test_auth.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

class TestAuthenticationSecurity:
    def test_no_authentication_required_critical(self):
        """Test that endpoints require authentication."""
        response = client.get("/api/v1/invoices/")
        assert response.status_code == 401  # Should require auth

        response = client.post("/api/v1/invoices/upload")
        assert response.status_code == 401  # Should require auth

    def test_fake_jwt_token_rejected(self):
        """Test that fake JWT tokens are rejected."""
        fake_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.fake.signature"
        headers = {"Authorization": f"Bearer {fake_token}"}

        response = client.get("/api/v1/invoices/", headers=headers)
        assert response.status_code == 401

    def test_sql_injection_protection(self):
        """Test SQL injection protection."""
        malicious_payloads = [
            "1' OR '1'='1",
            "1'; DROP TABLE users;--",
            "1' UNION SELECT * FROM users--"
        ]

        for payload in malicious_payloads:
            response = client.get(f"/api/v1/invoices/?vendor_id={payload}")
            # Should return 400 (bad request) or 401 (unauthorized), not 500 (server error)
            assert response.status_code in [400, 401, 422]

class TestFileUploadSecurity:
    def test_malicious_file_upload_blocked(self):
        """Test that malicious files are blocked."""
        # Test executable file
        files = {"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")}
        response = client.post("/api/v1/invoices/upload", files=files)
        assert response.status_code == 400

        # Test PHP file
        files = {"file": ("shell.php", b"<?php system($_GET['cmd']); ?>", "application/x-php")}
        response = client.post("/api/v1/invoices/upload", files=files)
        assert response.status_code == 400

    def test_file_size_limit(self):
        """Test file size limits."""
        large_content = b"A" * (50 * 1024 * 1024)  # 50MB
        files = {"file": ("large.pdf", large_content, "application/pdf")}
        response = client.post("/api/v1/invoices/upload", files=files)
        assert response.status_code == 413  # Request Entity Too Large
```

---

## 📋 IMPLEMENTATION CHECKLIST

### Phase 1: Critical Fixes (0-24 hours)
- [ ] Implement JWT authentication system
- [ ] Secure all database queries against SQL injection
- [ ] Implement secure file upload validation
- [ ] Add basic authentication middleware to all endpoints

### Phase 2: High Priority Fixes (1-3 days)
- [ ] Fix CORS configuration
- [ ] Add comprehensive security headers
- [ ] Remove hardcoded secrets
- [ ] Implement rate limiting
- [ ] Add input validation schemas

### Phase 3: Medium Priority Fixes (1-2 weeks)
- [ ] Implement error message sanitization
- [ ] Add comprehensive logging and monitoring
- [ ] Implement session management security
- [ ] Add automated security testing
- [ ] Create security incident response procedures

### Phase 4: Long-term Security (1-2 months)
- [ ] Implement Zero Trust architecture
- [ ] Add Web Application Firewall (WAF)
- [ ] Deploy security monitoring and alerting
- [ ] Conduct regular penetration testing
- [ ] Implement DevSecOps practices

---

## 🔍 VALIDATION AND TESTING

### Post-Implementation Testing
1. **Authentication Testing**
   - Verify all endpoints require authentication
   - Test JWT token validation
   - Verify role-based access control

2. **SQL Injection Testing**
   - Test with various SQL injection payloads
   - Verify parameterized queries are used
   - Check error messages don't reveal database info

3. **File Upload Testing**
   - Test malicious file uploads
   - Verify file type validation
   - Test file size limits
   - Check path traversal protection

4. **Security Headers Testing**
   - Verify all security headers are present
   - Test CORS configuration
   - Check CSP implementation

5. **Rate Limiting Testing**
   - Test rate limiting effectiveness
   - Verify rate limit bypass protection
   - Check rate limit error responses

### Continuous Monitoring
1. **Security Metrics**
   - Authentication failure rate
   - SQL injection attempt count
   - File upload rejection rate
   - Rate limiting activation frequency

2. **Alerting**
   - Immediate alerts for security events
   - Daily security summary reports
   - Weekly vulnerability scan results

3. **Regular Assessments**
   - Monthly security testing
   - Quarterly penetration testing
   - Annual security architecture review

---

**📞 SECURITY CONTACTS**
- **Security Team**: security@company.com
- **Incident Response**: incident@company.com
- **Vulnerability Disclosure**: security@company.com

**⚡ NEXT STEPS**
1. Review and approve this implementation plan
2. Assign development resources to critical fixes
3. Implement fixes in priority order
4. Test and validate each fix
5. Monitor for new security issues
6. Update security documentation

---

*This implementation guide should be followed step-by-step to ensure all security vulnerabilities are properly addressed. Each fix should be tested thoroughly before moving to the next step.*