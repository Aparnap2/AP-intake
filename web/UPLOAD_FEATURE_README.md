# Invoice Upload Feature

This document describes the implemented invoice upload functionality for the AP Intake system.

## Overview

The invoice upload feature allows users to upload PDF and image files for automated invoice processing. The system supports both drag-and-drop and file selection methods, with comprehensive error handling and progress tracking.

## Features

### 🎯 Core Functionality
- **Multiple File Upload**: Upload up to 10 files simultaneously
- **Drag & Drop Support**: Intuitive drag-and-drop interface
- **File Validation**: Automatic validation of file types and sizes
- **Progress Tracking**: Real-time upload progress for each file
- **Error Handling**: Graceful error handling with user-friendly messages

### 📁 Supported File Types
- **PDF Files** (preferred)
  - `.pdf`
- **Image Files**
  - `.png`
  - `.jpg`, `.jpeg`
  - `.tiff`, `.tif`

### 📏 File Limits
- **Maximum File Size**: 50MB per file
- **Maximum Files**: 10 files per upload session
- **Storage Type**: Configurable (local/S3/MinIO/R2/Supabase)

## Implementation Details

### Component Architecture

```
/web/components/invoice/UploadModal.tsx
├── File validation and management
├── Drag & drop handling
├── Progress tracking
├── API integration
└── Error handling

/web/lib/invoice-api.ts
├── API service layer
├── Request/response handling
├── Error management
└── TypeScript interfaces

/web/app/invoices/page.tsx
├── Modal integration
├── State management
└── Success callbacks

/web/components/invoice/InvoiceDashboard.tsx
├── Upload button integration
└── List refresh functionality
```

### API Integration

The upload feature integrates with the following API endpoints:

- `POST /api/v1/invoices/upload` - Upload invoice files
- `GET /api/v1/invoices` - Retrieve processed invoices
- `GET /api/v1/invoices/{id}` - Get specific invoice details

### State Management

The component manages the following states:
- **File List**: Selected files with metadata
- **Upload Progress**: Individual and overall progress
- **Validation States**: File validation results
- **Error States**: Upload error handling

## Usage

### End User Flow

1. Navigate to `/invoices` page
2. Click "Upload Invoice" button (available in header and dashboard)
3. Upload files using one of the following methods:
   - **Drag & Drop**: Drag files onto the upload area
   - **Click to Browse**: Click the upload area to open file picker
4. Review selected files in the file list
5. Click "Upload" to start processing
6. Monitor upload progress
7. View results and handle any errors

### Developer Integration

```tsx
import { UploadModal } from "@/components/invoice/UploadModal"

function MyComponent() {
  const [uploadModalOpen, setUploadModalOpen] = useState(false)

  const handleUploadSuccess = (invoices: any[]) => {
    console.log('Uploaded invoices:', invoices)
    // Refresh invoice list or update state
  }

  return (
    <>
      <Button onClick={() => setUploadModalOpen(true)}>
        Upload Invoice
      </Button>

      <UploadModal
        open={uploadModalOpen}
        onOpenChange={setUploadModalOpen}
        onSuccess={handleUploadSuccess}
      />
    </>
  )
}
```

## Error Handling

The system handles various error scenarios:

### File Validation Errors
- **Invalid File Type**: Shows supported file types
- **File Size Exceeded**: Displays size limit information
- **Duplicate Files**: Prevents uploading identical files
- **Maximum Files Reached**: Limits upload to 10 files

### Upload Errors
- **Network Errors**: Shows connection issues
- **API Errors**: Displays server response messages
- **Processing Errors**: Shows processing failure reasons
- **Timeout Errors**: Handles upload timeouts

### Recovery Mechanisms
- **Retry Failed Files**: Users can retry individual failed uploads
- **Remove Problematic Files**: Remove files that fail validation
- **Continue After Errors**: Upload remaining files even if some fail

## Testing

### Automated Tests

The feature includes comprehensive Playwright tests:

```bash
# Run all upload tests
npx playwright test tests/invoice-upload.spec.ts

# Run tests in headed mode
npx playwright test tests/invoice-upload.spec.ts --headed

# Run specific test
npx playwright test tests/invoice-upload.spec.ts -g "should open upload modal"
```

### Test Coverage

- ✅ Modal opening and closing
- ✅ Drag & drop functionality
- ✅ File validation
- ✅ Error handling
- ✅ Accessibility compliance
- ✅ Keyboard navigation
- ✅ API integration
- ✅ CORS configuration

### Manual Testing

1. **Start Services**:
   ```bash
   # Frontend
   npm run dev

   # Backend (if using Docker)
   docker-compose up -d
   ```

2. **Test Scenarios**:
   - Upload single PDF file
   - Upload multiple files
   - Test drag & drop
   - Test file validation (invalid types, oversized files)
   - Test network errors (disconnect during upload)
   - Test accessibility (keyboard navigation, screen readers)

## Configuration

### Environment Variables

```env
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# File Upload Configuration
MAX_FILE_SIZE=52428800  # 50MB in bytes
MAX_FILES=10
DOCLING_CONFIDENCE_THRESHOLD=0.8

# Storage Configuration
STORAGE_TYPE=local  # local/s3/r2/supabase
```

### Storage Backends

The system supports multiple storage backends:

- **Local Storage**: File system storage (development)
- **AWS S3**: Production cloud storage
- **Cloudflare R2**: Alternative cloud storage
- **Supabase Storage**: Integrated database storage

## Performance Considerations

### Frontend Optimizations
- **Lazy Loading**: Modal content loaded on demand
- **Progressive Enhancement**: Works without JavaScript
- **Memory Management**: Efficient file handling
- **Responsive Design**: Mobile-friendly interface

### Backend Optimizations
- **Streaming Upload**: Large files processed in chunks
- **Async Processing**: Background task processing
- **Rate Limiting**: Prevent abuse
- **Error Recovery**: Robust error handling

## Security Features

### File Security
- **Type Validation**: Server-side file type verification
- **Size Limits**: Prevent resource exhaustion
- **Virus Scanning**: Optional malware detection
- **Access Control**: User-based file access

### API Security
- **CORS Configuration**: Proper cross-origin handling
- **Authentication**: JWT-based user authentication
- **Authorization**: Role-based access control
- **Rate Limiting**: API usage limits

## Browser Compatibility

### Supported Browsers
- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

### Features by Browser
- **Drag & Drop**: All modern browsers
- **File API**: All modern browsers
- **Progress Tracking**: All modern browsers
- **Async/Await**: All modern browsers

## Troubleshooting

### Common Issues

#### Upload Fails
1. Check API server is running
2. Verify CORS configuration
3. Check network connectivity
4. Review browser console for errors

#### File Validation Errors
1. Verify file type is supported
2. Check file size doesn't exceed 50MB
3. Ensure file isn't corrupted
4. Check browser permissions

#### Progress Not Updating
1. Check API response format
2. Verify progress callback implementation
3. Review network conditions
4. Check browser developer tools

### Debug Information

Enable debug mode in browser console:

```javascript
// Log upload progress
localStorage.setItem('debugUpload', 'true')

// View network requests
// Check Network tab in DevTools

// Monitor console for errors
// Check Console tab in DevTools
```

## Future Enhancements

### Planned Features
- [ ] **Batch Operations**: Bulk upload management
- [ ] **Template Matching**: Automatic invoice categorization
- [ ] **OCR Preview**: Show extracted text before processing
- [ ] **Duplicate Detection**: Prevent duplicate invoice uploads
- [ ] **Upload History**: Track upload history and status
- [ ] **Advanced Validation**: Custom business rule validation

### Performance Improvements
- [ ] **Web Workers**: Background file processing
- [ ] **Compression**: Client-side file compression
- [ ] **Chunked Upload**: Large file handling
- [ ] **Caching**: Intelligent response caching

## Support

For issues or questions regarding the upload feature:

1. **Check Logs**: Review browser console and server logs
2. **Network Tab**: Monitor API requests in DevTools
3. **Documentation**: Refer to API documentation
4. **Test Environment**: Test in development environment first

## Changelog

### v1.0.0 (Current)
- ✅ Initial upload functionality
- ✅ Drag & drop support
- ✅ File validation
- ✅ Progress tracking
- ✅ Error handling
- ✅ API integration
- ✅ Comprehensive testing
- ✅ Documentation

---

*Last Updated: November 7, 2024*