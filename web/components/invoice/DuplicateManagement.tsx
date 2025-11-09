/**
 * Duplicate Management Component
 *
 * Comprehensive UI for managing duplicate invoices with resolution workflows.
 * Provides tools for reviewing, comparing, and resolving duplicate files.
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Clock,
  FileText,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Eye,
  Download,
  RefreshCw,
  Search,
  Filter,
  Trash2,
  Archive,
  Users,
  Scale,
  Calendar,
  HardDrive,
} from "lucide-react";

interface DuplicateRecord {
  id: string;
  ingestion_job_id: string;
  strategy: string;
  confidence_score: number;
  similarity_score?: number;
  match_criteria: Record<string, any>;
  comparison_details?: Record<string, any>;
  resolution_action?: string;
  resolved_by?: string;
  resolved_at?: string;
  resolution_notes?: string;
  requires_human_review: boolean;
  status: string;
  created_at: string;
  filename: string;
  file_size: number;
}

interface DuplicateGroup {
  group_id: string;
  duplicate_count: number;
  total_confidence: number;
  strategies_used: string[];
  duplicates: DuplicateRecord[];
}

interface DuplicateManagementProps {
  className?: string;
}

const DuplicateManagement: React.FC<DuplicateManagementProps> = ({ className }) => {
  const [duplicateGroups, setDuplicateGroups] = useState<DuplicateGroup[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<DuplicateGroup | null>(null);
  const [selectedDuplicates, setSelectedDuplicates] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resolutionDialog, setResolutionDialog] = useState(false);
  const [resolutionAction, setResolutionAction] = useState('');
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [strategyFilter, setStrategyFilter] = useState('all');
  const [viewMode, setViewMode] = useState<'groups' | 'duplicates'>('groups');

  // Resolution actions
  const resolutionActions = [
    { value: 'auto_ignore', label: 'Auto Ignore', description: 'Automatically ignore duplicate' },
    { value: 'auto_merge', label: 'Auto Merge', description: 'Merge data automatically' },
    { value: 'manual_review', label: 'Manual Review', description: 'Requires manual review' },
    { value: 'replace_existing', label: 'Replace Existing', description: 'Replace existing file' },
    { value: 'archive_existing', label: 'Archive Existing', description: 'Archive existing file' },
  ];

  // Strategy colors
  const strategyColors: Record<string, string> = {
    file_hash: 'bg-blue-100 text-blue-800',
    business_rules: 'bg-green-100 text-green-800',
    temporal: 'bg-yellow-100 text-yellow-800',
    fuzzy_matching: 'bg-purple-100 text-purple-800',
    composite: 'bg-red-100 text-red-800',
  };

  // Status colors
  const statusColors: Record<string, string> = {
    detected: 'bg-yellow-100 text-yellow-800',
    resolved: 'bg-green-100 text-green-800',
    ignored: 'bg-gray-100 text-gray-800',
    merged: 'bg-blue-100 text-blue-800',
  };

  // Load duplicate groups
  useEffect(() => {
    loadDuplicateGroups();
  }, [statusFilter, strategyFilter]);

  const loadDuplicateGroups = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (strategyFilter !== 'all') params.append('strategy', strategyFilter);

      const response = await fetch(`/api/v1/ingestion/duplicates?${params}`);
      if (!response.ok) {
        throw new Error('Failed to load duplicate groups');
      }

      const data = await response.json();
      setDuplicateGroups(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load duplicates');
    } finally {
      setLoading(false);
    }
  };

  const handleResolveDuplicates = async () => {
    if (!selectedDuplicates.length || !resolutionAction) return;

    setLoading(true);
    try {
      const promises = selectedDuplicates.map(duplicateId =>
        fetch(`/api/v1/ingestion/duplicates/${duplicateId}/resolve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            resolution: resolutionAction,
            resolved_by: 'current_user', // Would come from auth context
            resolution_notes: resolutionNotes,
          }),
        })
      );

      await Promise.all(promises);

      setResolutionDialog(false);
      setSelectedDuplicates([]);
      setResolutionAction('');
      setResolutionNotes('');
      loadDuplicateGroups();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve duplicates');
    } finally {
      setLoading(false);
    }
  };

  const handleResolveGroup = async (groupId: string, action: string) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/v1/ingestion/duplicates/groups/${groupId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resolution: action,
          resolved_by: 'current_user',
          resolution_notes: `Batch resolution: ${action}`,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to resolve group');
      }

      loadDuplicateGroups();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve group');
    } finally {
      setLoading(false);
    }
  };

  const downloadFile = async (jobId: string, filename: string) => {
    try {
      // Generate signed URL
      const signedUrlResponse = await fetch(`/api/v1/ingestion/jobs/${jobId}/signed-urls`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ max_access_count: 1 }),
      });

      if (!signedUrlResponse.ok) {
        throw new Error('Failed to generate download URL');
      }

      const { url } = await signedUrlResponse.json();

      // Download file
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to download file');
    }
  };

  const formatFileSize = (bytes: number) => {
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Bytes';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const calculateConfidenceLevel = (score: number) => {
    if (score >= 0.95) return { level: 'Very High', color: 'text-green-600' };
    if (score >= 0.85) return { level: 'High', color: 'text-blue-600' };
    if (score >= 0.70) return { level: 'Medium', color: 'text-yellow-600' };
    return { level: 'Low', color: 'text-red-600' };
  };

  const filteredGroups = duplicateGroups.filter(group =>
    group.duplicates.some(duplicate =>
      duplicate.filename.toLowerCase().includes(searchTerm.toLowerCase())
    )
  );

  const allDuplicates = filteredGroups.flatMap(group => group.duplicates);
  const filteredDuplicates = allDuplicates.filter(duplicate =>
    duplicate.filename.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Duplicate Management</h2>
          <p className="text-muted-foreground">
            Review and resolve duplicate invoice files
          </p>
        </div>
        <Button onClick={loadDuplicateGroups} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Groups</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{duplicateGroups.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Review</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {duplicateGroups.filter(g =>
                g.duplicates.some(d => d.requires_human_review)
              ).length}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Resolved</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {duplicateGroups.filter(g =>
                g.duplicates.every(d => d.status === 'resolved')
              ).length}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Confidence</CardTitle>
            <Scale className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {duplicateGroups.length > 0
                ? Math.round(
                    (duplicateGroups.reduce((sum, g) => sum + g.total_confidence, 0) /
                     duplicateGroups.length) * 100
                  ) + '%'
                : '0%'
              }
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters and Search */}
      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search files..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="detected">Detected</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="ignored">Ignored</SelectItem>
              </SelectContent>
            </Select>
            <Select value={strategyFilter} onValueChange={setStrategyFilter}>
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="Filter by strategy" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Strategies</SelectItem>
                <SelectItem value="file_hash">File Hash</SelectItem>
                <SelectItem value="business_rules">Business Rules</SelectItem>
                <SelectItem value="temporal">Temporal</SelectItem>
                <SelectItem value="fuzzy_matching">Fuzzy Matching</SelectItem>
                <SelectItem value="composite">Composite</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* View Mode Tabs */}
      <Tabs value={viewMode} onValueChange={(value) => setViewMode(value as 'groups' | 'duplicates')}>
        <TabsList>
          <TabsTrigger value="groups">Group View</TabsTrigger>
          <TabsTrigger value="duplicates">List View</TabsTrigger>
        </TabsList>

        <TabsContent value="groups" className="space-y-4">
          {/* Group View */}
          {filteredGroups.map((group) => (
            <Card key={group.group_id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <FileText className="h-5 w-5" />
                      Group {group.group_id.slice(0, 8)}...
                    </CardTitle>
                    <CardDescription>
                      {group.duplicate_count} duplicates • {group.strategies_used.length} strategies
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">
                      Confidence: {Math.round(group.total_confidence * 100)}%
                    </Badge>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedGroup(group)}
                    >
                      <Eye className="h-4 w-4 mr-2" />
                      View Details
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2 mb-4">
                  {group.strategies_used.map((strategy) => (
                    <Badge key={strategy} className={strategyColors[strategy]}>
                      {strategy.replace('_', ' ')}
                    </Badge>
                  ))}
                </div>
                <div className="text-sm text-muted-foreground">
                  Files: {group.duplicates.map(d => d.filename).join(', ')}
                </div>
              </CardContent>
              <CardFooter>
                <div className="flex justify-between w-full">
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleResolveGroup(group.group_id, 'auto_ignore')}
                    >
                      Ignore All
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleResolveGroup(group.group_id, 'manual_review')}
                    >
                      Mark for Review
                    </Button>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => {
                      setSelectedDuplicates(group.duplicates.map(d => d.id));
                      setResolutionDialog(true);
                    }}
                  >
                    Resolve Selected
                  </Button>
                </div>
              </CardFooter>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="duplicates">
          {/* List View */}
          <Card>
            <CardHeader>
              <CardTitle>All Duplicates</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <input
                        type="checkbox"
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedDuplicates(filteredDuplicates.map(d => d.id));
                          } else {
                            setSelectedDuplicates([]);
                          }
                        }}
                      />
                    </TableHead>
                    <TableHead>Filename</TableHead>
                    <TableHead>Strategy</TableHead>
                    <TableHead>Confidence</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDuplicates.map((duplicate) => (
                    <TableRow key={duplicate.id}>
                      <TableCell>
                        <input
                          type="checkbox"
                          checked={selectedDuplicates.includes(duplicate.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedDuplicates([...selectedDuplicates, duplicate.id]);
                            } else {
                              setSelectedDuplicates(selectedDuplicates.filter(id => id !== duplicate.id));
                            }
                          }}
                        />
                      </TableCell>
                      <TableCell className="font-medium">{duplicate.filename}</TableCell>
                      <TableCell>
                        <Badge className={strategyColors[duplicate.strategy]}>
                          {duplicate.strategy.replace('_', ' ')}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span>{Math.round(duplicate.confidence_score * 100)}%</span>
                          <Progress value={duplicate.confidence_score * 100} className="w-16" />
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={statusColors[duplicate.status] || 'bg-gray-100 text-gray-800'}>
                          {duplicate.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(duplicate.created_at)}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => downloadFile(duplicate.ingestion_job_id, duplicate.filename)}
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Batch Resolution Dialog */}
      <Dialog open={resolutionDialog} onOpenChange={setResolutionDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Resolve {selectedDuplicates.length} Duplicates</DialogTitle>
            <DialogDescription>
              Choose how to resolve the selected duplicate files.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="resolution-action">Resolution Action</Label>
              <Select value={resolutionAction} onValueChange={setResolutionAction}>
                <SelectTrigger>
                  <SelectValue placeholder="Select resolution action" />
                </SelectTrigger>
                <SelectContent>
                  {resolutionActions.map((action) => (
                    <SelectItem key={action.value} value={action.value}>
                      <div>
                        <div className="font-medium">{action.label}</div>
                        <div className="text-sm text-muted-foreground">{action.description}</div>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="resolution-notes">Resolution Notes</Label>
              <Textarea
                id="resolution-notes"
                placeholder="Add notes about this resolution..."
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setResolutionDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleResolveDuplicates}
              disabled={!resolutionAction || loading}
            >
              Resolve Duplicates
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Group Details Dialog */}
      <Dialog open={!!selectedGroup} onOpenChange={() => setSelectedGroup(null)}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Duplicate Group Details</DialogTitle>
            <DialogDescription>
              Detailed comparison of duplicate files in this group.
            </DialogDescription>
          </DialogHeader>
          {selectedGroup && (
            <div className="space-y-6">
              {/* Group Summary */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">{selectedGroup.duplicate_count}</div>
                    <p className="text-xs text-muted-foreground">Total Duplicates</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">
                      {Math.round(selectedGroup.total_confidence * 100)}%
                    </div>
                    <p className="text-xs text-muted-foreground">Avg Confidence</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">{selectedGroup.strategies_used.length}</div>
                    <p className="text-xs text-muted-foreground">Strategies Used</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">
                      {selectedGroup.duplicates.filter(d => d.requires_human_review).length}
                    </div>
                    <p className="text-xs text-muted-foreground">Need Review</p>
                  </CardContent>
                </Card>
              </div>

              {/* Duplicate Files */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold">Duplicate Files</h3>
                {selectedGroup.duplicates.map((duplicate) => (
                  <Card key={duplicate.id}>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4" />
                          <span className="font-medium">{duplicate.filename}</span>
                          <Badge className={strategyColors[duplicate.strategy]}>
                            {duplicate.strategy.replace('_', ' ')}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-muted-foreground">
                            {formatFileSize(duplicate.file_size)}
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => downloadFile(duplicate.ingestion_job_id, duplicate.filename)}
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <h4 className="font-medium mb-2">Match Criteria</h4>
                          <pre className="text-xs bg-muted p-2 rounded">
                            {JSON.stringify(duplicate.match_criteria, null, 2)}
                          </pre>
                        </div>
                        {duplicate.comparison_details && (
                          <div>
                            <h4 className="font-medium mb-2">Comparison Details</h4>
                            <pre className="text-xs bg-muted p-2 rounded">
                              {JSON.stringify(duplicate.comparison_details, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                      <div className="mt-4 flex items-center gap-4">
                        <div className="flex items-center gap-2">
                          <span className="text-sm">Confidence:</span>
                          <Progress value={duplicate.confidence_score * 100} className="w-24" />
                          <span className="text-sm font-medium">
                            {Math.round(duplicate.confidence_score * 100)}%
                          </span>
                        </div>
                        {duplicate.similarity_score && (
                          <div className="flex items-center gap-2">
                            <span className="text-sm">Similarity:</span>
                            <Progress value={duplicate.similarity_score * 100} className="w-24" />
                            <span className="text-sm font-medium">
                              {Math.round(duplicate.similarity_score * 100)}%
                            </span>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default DuplicateManagement;