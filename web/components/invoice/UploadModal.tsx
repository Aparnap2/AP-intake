"use client"

import { useState, useCallback, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert"
import { cn } from "@/lib/utils"
import { invoiceApi } from "@/lib/invoice-api"
import {
  Upload,
  File,
  X,
  AlertCircle,
  CheckCircle2,
  Loader2,
  FileImage,
  FileText,
  CloudUpload,
  Trash2
} from "lucide-react"

// Types
interface UploadFile {
  id: string
  file: File
  name: string
  size: number
  type: string
  status: "pending" | "uploading" | "success" | "error"
  progress: number
  error?: string
}

interface UploadModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: (invoices: any[]) => void
}

// Allowed file types
const ALLOWED_TYPES = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/tiff": [".tiff", ".tif"],
}

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB
const MAX_FILES = 10

export function UploadModal({ open, onOpenChange, onSuccess }: UploadModalProps) {
  const [files, setFiles] = useState<UploadFile[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateFile = (file: File): string | null => {
    // Check file type
    const isValidType = Object.keys(ALLOWED_TYPES).some(type => {
      if (file.type === type) return true
      return ALLOWED_TYPES[type as keyof typeof ALLOWED_TYPES].some(ext =>
        file.name.toLowerCase().endsWith(ext)
      )
    })

    if (!isValidType) {
      return "Invalid file type. Only PDF, PNG, JPG, JPEG, and TIFF files are allowed."
    }

    // Check file size
    if (file.size > MAX_FILE_SIZE) {
      return `File size exceeds ${MAX_FILE_SIZE / 1024 / 1024}MB limit.`
    }

    return null
  }

  const addFiles = (newFiles: FileList) => {
    const validFiles: UploadFile[] = []
    const errors: string[] = []

    Array.from(newFiles).forEach(file => {
      // Check if we've reached max files
      if (files.length + validFiles.length >= MAX_FILES) {
        errors.push(`Cannot add ${file.name}. Maximum ${MAX_FILES} files allowed.`)
        return
      }

      const error = validateFile(file)
      if (error) {
        errors.push(`${file.name}: ${error}`)
        return
      }

      // Check for duplicates
      if (files.some(f => f.name === file.name && f.size === file.size)) {
        errors.push(`${file.name}: File already added.`)
        return
      }

      validFiles.push({
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        file,
        name: file.name,
        size: file.size,
        type: file.type,
        status: "pending",
        progress: 0,
      })
    })

    if (errors.length > 0) {
      console.error("File validation errors:", errors)
    }

    setFiles(prev => [...prev, ...validFiles])
  }

  const removeFile = (id: string) => {
    setFiles(prev => prev.filter(f => f.id !== id))
  }

  const clearFiles = () => {
    setFiles([])
    setUploadProgress(0)
  }

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const droppedFiles = e.dataTransfer.files
    if (droppedFiles.length > 0) {
      addFiles(droppedFiles)
    }
  }, [files])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files
    if (selectedFiles && selectedFiles.length > 0) {
      addFiles(selectedFiles)
    }
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  const uploadFile = async (uploadFile: UploadFile): Promise<any> => {
    try {
      const result = await invoiceApi.uploadInvoice(uploadFile.file, (progress) => {
        setFiles(prev => prev.map(f =>
          f.id === uploadFile.id
            ? { ...f, progress }
            : f
        ))
      })
      return result
    } catch (error) {
      throw error
    }
  }

  const handleUpload = async () => {
    if (files.length === 0) return

    setIsUploading(true)
    setUploadProgress(0)

    const results: any[] = []
    const totalFiles = files.filter(f => f.status === "pending").length
    let completedFiles = 0

    try {
      // Update files to uploading status
      setFiles(prev => prev.map(f =>
        f.status === "pending"
          ? { ...f, status: "uploading", progress: 0 }
          : f
      ))

      // Upload files one by one
      for (const uploadFile of files.filter(f => f.status === "uploading")) {
        try {
          setFiles(prev => prev.map(f =>
            f.id === uploadFile.id
              ? { ...f, progress: 0 }
              : f
          ))

          const result = await uploadFile(uploadFile)

          setFiles(prev => prev.map(f =>
            f.id === uploadFile.id
              ? { ...f, status: "success", progress: 100 }
              : f
          ))

          results.push(result)
          completedFiles++
          setUploadProgress((completedFiles / totalFiles) * 100)

        } catch (error) {
          console.error(`Failed to upload ${uploadFile.name}:`, error)

          setFiles(prev => prev.map(f =>
            f.id === uploadFile.id
              ? {
                  ...f,
                  status: "error",
                  error: error instanceof Error ? error.message : "Upload failed"
                }
              : f
          ))

          completedFiles++
          setUploadProgress((completedFiles / totalFiles) * 100)
        }
      }

      // Call success callback with results
      if (results.length > 0 && onSuccess) {
        onSuccess(results)
      }

    } catch (error) {
      console.error("Upload process failed:", error)
    } finally {
      setIsUploading(false)
    }
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes"
    const k = 1024
    const sizes = ["Bytes", "KB", "MB", "GB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
  }

  const getFileIcon = (type: string) => {
    if (type === "application/pdf") {
      return <FileText className="w-5 h-5 text-red-500" />
    }
    return <FileImage className="w-5 h-5 text-blue-500" />
  }

  const hasPendingFiles = files.some(f => f.status === "pending")
  const hasUploadingFiles = files.some(f => f.status === "uploading")
  const allComplete = files.length > 0 && files.every(f => f.status === "success" || f.status === "error")

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Upload className="w-5 h-5" />
            Upload Invoices
          </DialogTitle>
          <DialogDescription>
            Upload PDF or image files for invoice processing. Supports drag-and-drop.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Upload Area */}
          <div
            className={cn(
              "relative border-2 border-dashed rounded-lg p-8 text-center transition-colors",
              isDragging
                ? "border-blue-500 bg-blue-50"
                : "border-gray-300 hover:border-gray-400",
              files.length > 0 && "border-gray-200"
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={Object.keys(ALLOWED_TYPES).join(",")}
              onChange={handleFileSelect}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              disabled={isUploading}
            />

            <div className="space-y-4">
              <div className="flex justify-center">
                <CloudUpload className={cn(
                  "w-12 h-12 transition-colors",
                  isDragging ? "text-blue-500" : "text-gray-400"
                )} />
              </div>

              <div>
                <p className="text-lg font-medium">
                  {isDragging ? "Drop files here" : "Drop invoice files here"}
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  or click to browse
                </p>
              </div>

              <div className="flex flex-wrap justify-center gap-2 text-xs text-gray-500">
                <span className="px-2 py-1 bg-gray-100 rounded">PDF</span>
                <span className="px-2 py-1 bg-gray-100 rounded">PNG</span>
                <span className="px-2 py-1 bg-gray-100 rounded">JPG</span>
                <span className="px-2 py-1 bg-gray-100 rounded">JPEG</span>
                <span className="px-2 py-1 bg-gray-100 rounded">TIFF</span>
              </div>

              <p className="text-xs text-gray-500">
                Maximum file size: {MAX_FILE_SIZE / 1024 / 1024}MB • Maximum files: {MAX_FILES}
              </p>
            </div>
          </div>

          {/* File List */}
          {files.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">Files ({files.length})</h4>
                {!isUploading && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={clearFiles}
                    className="text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="w-4 h-4 mr-1" />
                    Clear All
                  </Button>
                )}
              </div>

              <div className="space-y-2 max-h-64 overflow-y-auto">
                {files.map((file) => (
                  <div
                    key={file.id}
                    className={cn(
                      "flex items-center gap-3 p-3 border rounded-lg",
                      file.status === "error" && "border-red-200 bg-red-50",
                      file.status === "success" && "border-green-200 bg-green-50"
                    )}
                  >
                    {getFileIcon(file.type)}

                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{file.name}</p>
                      <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>

                      {file.status === "uploading" && (
                        <div className="mt-1">
                          <Progress value={file.progress} className="h-1" />
                        </div>
                      )}

                      {file.status === "error" && (
                        <p className="text-xs text-red-600 mt-1">{file.error}</p>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      {file.status === "pending" && !isUploading && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeFile(file.id)}
                          className="text-red-600 hover:text-red-700 h-8 w-8 p-0"
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      )}

                      {file.status === "uploading" && (
                        <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                      )}

                      {file.status === "success" && (
                        <CheckCircle2 className="w-5 h-5 text-green-500" />
                      )}

                      {file.status === "error" && (
                        <AlertCircle className="w-5 h-5 text-red-500" />
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Overall Progress */}
              {isUploading && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span>Overall Progress</span>
                    <span>{Math.round(uploadProgress)}%</span>
                  </div>
                  <Progress value={uploadProgress} className="h-2" />
                </div>
              )}
            </div>
          )}

          {/* Upload Status Messages */}
          {allComplete && !isUploading && (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertTitle>Upload Complete</AlertTitle>
              <AlertDescription>
                {files.filter(f => f.status === "success").length} file(s) uploaded successfully.
                {files.filter(f => f.status === "error").length > 0 && (
                  <span> {files.filter(f => f.status === "error").length} file(s) failed.</span>
                )}
              </AlertDescription>
            </Alert>
          )}

          {/* Action Buttons */}
          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={hasUploadingFiles}
            >
              {allComplete ? "Close" : "Cancel"}
            </Button>

            {hasPendingFiles && !isUploading && (
              <Button onClick={handleUpload} className="min-w-24">
                <Upload className="w-4 h-4 mr-2" />
                Upload {files.filter(f => f.status === "pending").length}
                {files.filter(f => f.status === "pending").length === 1 ? " File" : " Files"}
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}