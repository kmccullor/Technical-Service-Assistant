'use client'

import React, { useState, useEffect } from 'react'
import { 
  Database, 
  Table2, 
  Columns, 
  Eye, 
  Plus, 
  Download,
  Upload,
  GitCompare,
  Settings,
  Search,
  Filter,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

interface RNIVersion {
  id: number
  version_number: string
  version_name: string
  description: string
  release_date: string
  is_active: boolean
}

interface DatabaseInstance {
  id: number
  rni_version_id: number
  database_name: string
  database_type: string
  server_name: string
  port: number
  description: string
  is_active: boolean
}

interface SchemaOverview {
  version_number: string
  version_name: string
  database_name: string
  database_type: string
  schema_name: string
  table_name: string
  table_type: string
  table_description: string
  row_count: number
  column_count: number
  table_created_at: string
}

interface ColumnDetails {
  version_number: string
  database_name: string
  database_type: string
  schema_name: string
  table_name: string
  column_name: string
  ordinal_position: number
  data_type: string
  max_length: number | null
  precision_value: number | null
  scale_value: number | null
  is_nullable: boolean
  is_primary_key: boolean
  is_foreign_key: boolean
  is_identity: boolean
  default_value: string | null
  description: string | null
}

interface SchemaExtractionRequest {
  rni_version_id: number
  database_type: 'MSSQL' | 'PostgreSQL'
  server: string
  port: number
  database: string
  username: string
  password: string
  schema_name?: string
  created_by?: string
}

export default function DataDictionaryManager() {
  const [rniVersions, setRniVersions] = useState<RNIVersion[]>([])
  const [selectedVersion, setSelectedVersion] = useState<string>('')
  const [schemaOverview, setSchemaOverview] = useState<SchemaOverview[]>([])
  const [columnDetails, setColumnDetails] = useState<ColumnDetails[]>([])
  const [databaseInstances, setDatabaseInstances] = useState<DatabaseInstance[]>([])
  
  const [isLoading, setIsLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedDatabase, setSelectedDatabase] = useState('')
  const [selectedSchema, setSelectedSchema] = useState('')
  const [selectedTable, setSelectedTable] = useState('')
  
  // Schema upload form
  const [extractionDialogOpen, setExtractionDialogOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadForm, setUploadForm] = useState({
    rni_version_id: 0,
    database_type: 'PostgreSQL' as 'MSSQL' | 'PostgreSQL',
    database_name: '',
    created_by: ''
  })
  const [showQueryHelp, setShowQueryHelp] = useState(false)

  // Version comparison
  const [comparisonDialogOpen, setComparisonDialogOpen] = useState(false)
  const [version1, setVersion1] = useState('')
  const [version2, setVersion2] = useState('')
  const [comparisonResults, setComparisonResults] = useState<any>(null)

  useEffect(() => {
    fetchRNIVersions()
    // Load initial data for the active version
    const loadInitialData = async () => {
      try {
        const response = await fetch('/api/reranker/data-dictionary/rni-versions')
        const versions = await response.json()
        const activeVersion = versions.find((v: RNIVersion) => v.is_active)
        if (activeVersion) {
          setSelectedVersion(activeVersion.version_number)
        }
      } catch (error) {
        console.error('Failed to set initial version:', error)
      }
    }
    loadInitialData()
  }, [])

  useEffect(() => {
    if (selectedVersion) {
      fetchSchemaOverview()
      fetchDatabaseInstances()
    }
  }, [selectedVersion])

  useEffect(() => {
    if (selectedVersion) {
      fetchSchemaOverview()
    }
  }, [selectedDatabase, selectedSchema])

  useEffect(() => {
    if (selectedVersion) {
      fetchSchemaOverview()
      fetchDatabaseInstances()
    }
  }, [selectedVersion, selectedDatabase, selectedSchema])

  const fetchRNIVersions = async () => {
    try {
      const response = await fetch('/api/reranker/data-dictionary/rni-versions')
      const data = await response.json()
      setRniVersions(data)
      if (data.length > 0 && !selectedVersion) {
        const activeVersion = data.find((v: RNIVersion) => v.is_active) || data[0]
        setSelectedVersion(activeVersion.version_number)
      }
    } catch (error) {
      console.error('Failed to fetch RNI versions:', error)
    }
  }

  const fetchSchemaOverview = async () => {
    setIsLoading(true)
    try {
      const params = new URLSearchParams()
      if (selectedVersion) params.append('version_number', selectedVersion)
      if (selectedDatabase) params.append('database_name', selectedDatabase)
      if (selectedSchema) params.append('schema_name', selectedSchema)

      const response = await fetch(`/api/reranker/data-dictionary/schema-overview?${params}`)
      const data = await response.json()
      setSchemaOverview(data)
    } catch (error) {
      console.error('Failed to fetch schema overview:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const fetchDatabaseInstances = async () => {
    if (!selectedVersion) return
    
    try {
      const selectedVersionObj = rniVersions.find(v => v.version_number === selectedVersion)
      if (!selectedVersionObj) return

      const response = await fetch(`/api/reranker/data-dictionary/database-instances?rni_version_id=${selectedVersionObj.id}`)
      const data = await response.json()
      setDatabaseInstances(data)
    } catch (error) {
      console.error('Failed to fetch database instances:', error)
    }
  }

  const fetchColumnDetails = async (tableName: string) => {
    try {
      const params = new URLSearchParams()
      if (selectedVersion) params.append('version_number', selectedVersion)
      if (selectedDatabase) params.append('database_name', selectedDatabase)
      if (selectedSchema) params.append('schema_name', selectedSchema)
      if (tableName) params.append('table_name', tableName)

      const response = await fetch(`/api/reranker/data-dictionary/column-details?${params}`)
      const data = await response.json()
      setColumnDetails(data)
      setSelectedTable(tableName)
    } catch (error) {
      console.error('Failed to fetch column details:', error)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
      .then(() => alert('Query copied to clipboard!'))
      .catch(err => console.error('Failed to copy text: ', err))
  }

  const handleSchemaUpload = async () => {
    if (!selectedFile) return
    
    setIsLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('rni_version_id', uploadForm.rni_version_id.toString())
      formData.append('database_type', uploadForm.database_type)
      formData.append('database_name', uploadForm.database_name)
      formData.append('created_by', uploadForm.created_by)

      const response = await fetch('/api/data-dictionary/upload-schema', {
        method: 'POST',
        body: formData
      })

      if (response.ok) {
        const result = await response.json()
        alert(`Schema upload successful! Imported ${result.statistics?.tables || 0} tables and ${result.statistics?.columns || 0} columns.`)
        setExtractionDialogOpen(false)
        setSelectedFile(null)
        fetchSchemaOverview()
        fetchDatabaseInstances()
      } else {
        const error = await response.json()
        alert(`Schema upload failed: ${error.detail || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Schema upload error:', error)
      alert('Schema upload failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSchemaComparison = async () => {
    if (!version1 || !version2) return

    setIsLoading(true)
    try {
      const params = new URLSearchParams({
        version1,
        version2
      })
      if (selectedDatabase) params.append('database_name', selectedDatabase)

      const response = await fetch(`/api/reranker/data-dictionary/compare-schemas?${params}`)
      const data = await response.json()
      setComparisonResults(data)
    } catch (error) {
      console.error('Failed to compare schemas:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const filteredSchemaOverview = schemaOverview.filter(item => {
    // Apply database filter
    if (selectedDatabase && item.database_name !== selectedDatabase) {
      return false
    }
    
    // Apply schema filter
    if (selectedSchema && item.schema_name !== selectedSchema) {
      return false
    }
    
    // Apply search term filter
    if (searchTerm) {
      const searchLower = searchTerm.toLowerCase()
      return (
        item.table_name.toLowerCase().includes(searchLower) ||
        item.schema_name.toLowerCase().includes(searchLower) ||
        item.database_name.toLowerCase().includes(searchLower) ||
        (item.table_description || '').toLowerCase().includes(searchLower)
      )
    }
    
    return true
  })

  const uniqueDatabases = [...new Set(schemaOverview.map(item => item.database_name))]
  const uniqueSchemas = [...new Set(schemaOverview
    .filter(item => !selectedDatabase || item.database_name === selectedDatabase)
    .map(item => item.schema_name))]

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Database className="h-8 w-8" />
            Data Dictionary Manager
          </h1>
          <p className="text-muted-foreground">
            Manage database schemas for MSSQL and PostgreSQL databases by RNI version
          </p>
        </div>
        <div className="flex gap-2">
          <Dialog open={extractionDialogOpen} onOpenChange={setExtractionDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Upload className="h-4 w-4 mr-2" />
                Upload Schema
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Upload Database Schema</DialogTitle>
                <DialogDescription>
                  Upload schema data for Sensus AMI databases. You'll need to run the provided SQL query on your database and upload the CSV results.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="rni_version">RNI Version</Label>
                    <Select
                      value={uploadForm.rni_version_id.toString()}
                      onValueChange={(value) => setUploadForm(prev => ({ ...prev, rni_version_id: parseInt(value) }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select RNI Version" />
                      </SelectTrigger>
                      <SelectContent>
                        {rniVersions.map(version => (
                          <SelectItem key={version.id} value={version.id.toString()}>
                            {version.version_number} - {version.version_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="database_type">Database Type</Label>
                    <Select
                      value={uploadForm.database_type}
                      onValueChange={(value: string) => setUploadForm(prev => ({ 
                        ...prev, 
                        database_type: value as 'MSSQL' | 'PostgreSQL'
                      }))}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="PostgreSQL">PostgreSQL</SelectItem>
                        <SelectItem value="MSSQL">Microsoft SQL Server</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                
                <div>
                  <Label htmlFor="database_name">Database Name</Label>
                  <Input
                    id="database_name"
                    value={uploadForm.database_name}
                    onChange={(e) => setUploadForm(prev => ({ ...prev, database_name: e.target.value }))}
                    placeholder="e.g., FlexnetDB, AMDS, Router, FWDL"
                  />
                </div>
                
                <div>
                  <Label htmlFor="schema_file">Schema CSV File</Label>
                  <Input
                    id="schema_file"
                    type="file"
                    accept=".csv"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    className="cursor-pointer"
                  />
                  <p className="text-sm text-gray-500 mt-1">
                    Upload a CSV file generated by running the extraction query on your database. See the query help section below.
                  </p>
                </div>
                
                <div>
                  <Label htmlFor="created_by">Created By</Label>
                  <Input
                    id="created_by"
                    value={uploadForm.created_by}
                    onChange={(e) => setUploadForm(prev => ({ ...prev, created_by: e.target.value }))}
                    placeholder="Your name or username"
                  />
                </div>
                
                <div className="border rounded-lg p-4 bg-amber-50 border-amber-200">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-medium text-amber-800">📋 Schema Extraction Query</h4>
                    <Button 
                      type="button"
                      variant="outline" 
                      onClick={() => setShowQueryHelp(!showQueryHelp)}
                      className="text-xs"
                    >
                      {showQueryHelp ? 'Hide' : 'Show'} Query
                    </Button>
                  </div>
                  
                  {showQueryHelp && (
                    <div className="space-y-3">
                      <p className="text-sm text-amber-700">
                        <strong>⚠️ Important:</strong> You must run this query on your {uploadForm.database_type} database to generate the CSV file for upload:
                      </p>
                      
                      <div className="relative bg-gray-900 text-gray-100 p-3 rounded text-xs font-mono overflow-x-auto">
                        <Button 
                          type="button"
                          variant="outline"
                          onClick={() => copyToClipboard(uploadForm.database_type === 'MSSQL' ? getMSSQLQuery(uploadForm.database_name) : getPostgreSQLQuery(uploadForm.database_name))}
                          className="absolute top-2 right-2 h-6 px-2 text-xs bg-gray-700 hover:bg-gray-600 border-gray-600"
                        >
                          📋 Copy
                        </Button>
                        <pre className="whitespace-pre-wrap pr-16">
                          {uploadForm.database_type === 'MSSQL' ? getMSSQLQuery(uploadForm.database_name) : getPostgreSQLQuery(uploadForm.database_name)}
                        </pre>
                      </div>
                      
                      <div className="text-xs text-amber-700 bg-white p-3 rounded border">
                        <p><strong>📝 Step-by-step Instructions:</strong></p>
                        <ol className="list-decimal list-inside space-y-1 mt-2">
                          <li>Copy the SQL query above</li>
                          <li>Connect to your {uploadForm.database_name} database</li>
                          <li>Execute the query in your SQL client</li>
                          <li>Export the query results as a CSV file</li>
                          <li>Upload the generated CSV file using the file selector above</li>
                        </ol>
                        <p className="mt-2 text-amber-600">
                          <strong>Note:</strong> This system cannot directly access your database servers. You must generate and upload the schema data manually.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setExtractionDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleSchemaUpload} disabled={isLoading || !selectedFile}>
                  {isLoading ? 'Uploading...' : 'Upload Schema'}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
          
          <Dialog open={comparisonDialogOpen} onOpenChange={setComparisonDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline">
                <GitCompare className="h-4 w-4 mr-2" />
                Compare Versions
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Compare Schema Versions</DialogTitle>
                <DialogDescription>
                  Compare database schemas between two RNI versions
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="version1">Version 1</Label>
                    <Select value={version1} onValueChange={setVersion1}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select first version" />
                      </SelectTrigger>
                      <SelectContent>
                        {rniVersions.map(version => (
                          <SelectItem key={version.id} value={version.version_number}>
                            {version.version_number}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="version2">Version 2</Label>
                    <Select value={version2} onValueChange={setVersion2}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select second version" />
                      </SelectTrigger>
                      <SelectContent>
                        {rniVersions.map(version => (
                          <SelectItem key={version.id} value={version.version_number}>
                            {version.version_number}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <Button onClick={handleSchemaComparison} disabled={!version1 || !version2 || isLoading}>
                  {isLoading ? 'Comparing...' : 'Compare Schemas'}
                </Button>
                
                {comparisonResults && (
                  <div className="mt-4 space-y-2">
                    <h4 className="font-medium">Comparison Results:</h4>
                    <div className="max-h-60 overflow-y-auto">
                      {comparisonResults.changes.map((change: any, index: number) => (
                        <div key={index} className="flex items-center justify-between p-2 bg-muted rounded">
                          <span className="text-sm">
                            {change.schema_name}.{change.table_name}.{change.column_name}
                          </span>
                          <Badge variant={
                            change.change_type === 'ADDED' ? 'default' :
                            change.change_type === 'REMOVED' ? 'destructive' : 'secondary'
                          }>
                            {change.change_type}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <Label>RNI Version</Label>
              <Select value={selectedVersion} onValueChange={(value) => {
                setSelectedVersion(value)
                setSelectedDatabase('') // Reset filters when version changes
                setSelectedSchema('')
                setColumnDetails([]) // Clear column details
                setSelectedTable('')
              }}>
                <SelectTrigger>
                  <SelectValue placeholder="Select RNI Version" />
                </SelectTrigger>
                <SelectContent>
                  {rniVersions.map(version => (
                    <SelectItem key={version.id} value={version.version_number}>
                      {version.version_number}
                      {version.is_active && <Badge className="ml-2">Active</Badge>}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Database</Label>
              <Select value={selectedDatabase} onValueChange={(value) => {
                setSelectedDatabase(value)
                setSelectedSchema('') // Reset schema when database changes
              }}>
                <SelectTrigger>
                  <SelectValue placeholder="All Databases" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All Databases</SelectItem>
                  {uniqueDatabases.map(database => (
                    <SelectItem key={database} value={database}>
                      {database}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Schema</Label>
              <Select value={selectedSchema} onValueChange={setSelectedSchema}>
                <SelectTrigger>
                  <SelectValue placeholder="All Schemas" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All Schemas</SelectItem>
                  {uniqueSchemas.map(schema => (
                    <SelectItem key={schema} value={schema}>
                      {schema}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Search Tables</Label>
              <Input
                placeholder="Search tables..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Schema Overview</TabsTrigger>
          <TabsTrigger value="columns">Column Details</TabsTrigger>
          <TabsTrigger value="instances">Database Instances</TabsTrigger>
          <TabsTrigger value="ami-assistant">Technical Services Assistant</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Table2 className="h-5 w-5" />
                  Schema Overview ({filteredSchemaOverview.length} tables)
                </span>
                <Button variant="outline" size="sm">
                  <Download className="h-4 w-4 mr-2" />
                  Export
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Clock className="h-6 w-6 animate-spin mr-2" />
                  Loading schema data...
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-2">Database</th>
                        <th className="text-left p-2">Schema</th>
                        <th className="text-left p-2">Table</th>
                        <th className="text-left p-2">Type</th>
                        <th className="text-left p-2">Columns</th>
                        <th className="text-left p-2">Rows</th>
                        <th className="text-left p-2">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredSchemaOverview.map((item, index) => (
                        <tr key={index} className="border-b hover:bg-muted/50">
                          <td className="p-2">
                            <div className="flex items-center gap-1">
                              <Database className="h-4 w-4" />
                              {item.database_name}
                              <Badge variant="outline">
                                {item.database_type}
                              </Badge>
                            </div>
                          </td>
                          <td className="p-2">{item.schema_name}</td>
                          <td className="p-2">
                            <div>
                              <div className="font-medium">{item.table_name}</div>
                              {item.table_description && (
                                <div className="text-xs text-muted-foreground">
                                  {item.table_description}
                                </div>
                              )}
                            </div>
                          </td>
                          <td className="p-2">
                            <Badge variant={item.table_type === 'TABLE' ? 'default' : 'secondary'}>
                              {item.table_type}
                            </Badge>
                          </td>
                          <td className="p-2">{item.column_count}</td>
                          <td className="p-2">
                            {item.row_count !== null ? item.row_count.toLocaleString() : 'N/A'}
                          </td>
                          <td className="p-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => fetchColumnDetails(item.table_name)}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="columns">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Columns className="h-5 w-5" />
                Column Details
                {selectedTable && <span className="text-muted-foreground">- {selectedTable}</span>}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {columnDetails.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-2">#</th>
                        <th className="text-left p-2">Column Name</th>
                        <th className="text-left p-2">Data Type</th>
                        <th className="text-left p-2">Nullable</th>
                        <th className="text-left p-2">Key</th>
                        <th className="text-left p-2">Default</th>
                        <th className="text-left p-2">Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {columnDetails.map((column, index) => (
                        <tr key={index} className="border-b hover:bg-muted/50">
                          <td className="p-2">{column.ordinal_position}</td>
                          <td className="p-2 font-medium">{column.column_name}</td>
                          <td className="p-2">
                            <code className="text-sm bg-muted px-1 rounded">
                              {column.data_type}
                              {column.max_length && `(${column.max_length})`}
                              {column.precision_value && column.scale_value && 
                                `(${column.precision_value},${column.scale_value})`}
                            </code>
                          </td>
                          <td className="p-2">
                            {column.is_nullable ? (
                              <CheckCircle className="h-4 w-4 text-green-500" />
                            ) : (
                              <XCircle className="h-4 w-4 text-red-500" />
                            )}
                          </td>
                          <td className="p-2">
                            <div className="flex gap-1">
                              {column.is_primary_key && <Badge>PK</Badge>}
                              {column.is_foreign_key && <Badge variant="outline">FK</Badge>}
                              {column.is_identity && <Badge variant="secondary">ID</Badge>}
                            </div>
                          </td>
                          <td className="p-2 text-sm text-muted-foreground">
                            {column.default_value || '-'}
                          </td>
                          <td className="p-2 text-sm text-muted-foreground">
                            {column.description || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  Select a table from the Schema Overview to view column details
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="instances">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="h-5 w-5" />
                Database Instances
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4">
                {databaseInstances.map((instance) => (
                  <Card key={instance.id} className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-medium flex items-center gap-2">
                          <Database className="h-4 w-4" />
                          {instance.database_name}
                          <Badge variant="outline">{instance.database_type}</Badge>
                          {instance.is_active && <Badge>Active</Badge>}
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          {instance.server_name}:{instance.port}
                        </p>
                        {instance.description && (
                          <p className="text-sm text-muted-foreground mt-1">
                            {instance.description}
                          </p>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm">
                          <Settings className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ami-assistant">
          <TechnicalServicesAssistant />
        </TabsContent>
      </Tabs>
    </div>
  )
}

// Helper functions for generating extraction queries
function getMSSQLQuery(databaseName: string): string {
  return `-- Sensus AMI ${databaseName} Schema Extraction Query (MSSQL)
-- Run this query to extract schema information for data dictionary import

SELECT 
    s.name AS schema_name,
    t.name AS table_name,
    c.name AS column_name,
    ty.name AS data_type,
    c.max_length,
    c.precision,
    c.scale,
    c.is_nullable,
    c.is_identity,
    CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key,
    ISNULL(cc.definition, '') AS default_value,
    ISNULL(ep.value, '') AS column_description
FROM sys.tables t
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
INNER JOIN sys.columns c ON t.object_id = c.object_id
INNER JOIN sys.types ty ON c.user_type_id = ty.user_type_id
LEFT JOIN (
    SELECT 
        ic.object_id,
        ic.column_id,
        c.name AS column_name
    FROM sys.indexes i
    INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
    INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
    WHERE i.is_primary_key = 1
) pk ON t.object_id = pk.object_id AND c.column_id = pk.column_id
LEFT JOIN sys.default_constraints cc ON c.default_object_id = cc.object_id
LEFT JOIN sys.extended_properties ep ON t.object_id = ep.major_id AND c.column_id = ep.minor_id AND ep.name = 'MS_Description'
WHERE t.type = 'U'  -- User tables only
ORDER BY s.name, t.name, c.column_id;`
}

function getPostgreSQLQuery(databaseName: string): string {
  return `-- Sensus AMI ${databaseName} Schema Extraction Query (PostgreSQL)
-- Run this query to extract schema information for data dictionary import

SELECT 
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attname AS column_name,
    t.typname AS data_type,
    CASE WHEN a.attlen > 0 THEN a.attlen ELSE a.atttypmod - 4 END AS max_length,
    0 AS precision,  -- PostgreSQL specific handling would go here
    0 AS scale,      -- PostgreSQL specific handling would go here
    NOT a.attnotnull AS is_nullable,
    CASE WHEN a.attidentity != '' THEN true ELSE false END AS is_identity,
    CASE WHEN pk.attname IS NOT NULL THEN true ELSE false END AS is_primary_key,
    COALESCE(ad.adsrc, '') AS default_value,
    COALESCE(d.description, '') AS column_description
FROM pg_class c
JOIN pg_namespace n ON c.relnamespace = n.oid
JOIN pg_attribute a ON c.oid = a.attrelid
JOIN pg_type t ON a.atttypid = t.oid
LEFT JOIN pg_attrdef ad ON a.attrelid = ad.adrelid AND a.attnum = ad.adnum
LEFT JOIN pg_description d ON c.oid = d.objoid AND a.attnum = d.objsubid
LEFT JOIN (
    SELECT 
        i.indrelid,
        a.attname,
        a.attnum
    FROM pg_index i
    JOIN pg_attribute a ON i.indrelid = a.attrelid AND a.attnum = ANY(i.indkey)
    WHERE i.indisprimary = true
) pk ON c.oid = pk.indrelid AND a.attnum = pk.attnum
WHERE c.relkind = 'r'  -- Regular tables only
  AND n.nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
  AND a.attnum > 0     -- Exclude system columns
  AND NOT a.attisdropped
ORDER BY n.nspname, c.relname, a.attnum;`
}

// Technical Services Assistant Component
function TechnicalServicesAssistant() {
  const [rniVersion, setRniVersion] = useState('')
  const [databaseName, setDatabaseName] = useState('')
  const [queryResult, setQueryResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [availableVersions, setAvailableVersions] = useState<RNIVersion[]>([])

  // Load available RNI versions
  useEffect(() => {
    fetch('/api/data-dictionary/rni-versions')
      .then(res => res.json())
      .then(data => setAvailableVersions(data))
      .catch(err => console.error('Failed to load RNI versions:', err))
  }, [])

  const handleQueryAssistance = async () => {
    if (!rniVersion || !databaseName) {
      alert('Please select both RNI version and database name')
      return
    }

    setLoading(true)
    try {
      const response = await fetch('/api/data-dictionary/query-assistance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rni_version: rniVersion, database_name: databaseName })
      })
      const data = await response.json()
      setQueryResult(data)
    } catch (error) {
      console.error('Query assistance failed:', error)
      setQueryResult({ status: 'error', message: 'Failed to get query assistance' })
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    alert('Copied to clipboard!')
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-5 w-5" />
            Technical Services Assistant
          </CardTitle>
          <CardDescription>
            Get help with database queries for Sensus AMI Infrastructure. Check if schema data is available or get SQL queries to extract schema information for upload.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="rni-version">RNI Version *</Label>
              <Select value={rniVersion} onValueChange={setRniVersion}>
                <SelectTrigger>
                  <SelectValue placeholder="Select RNI version" />
                </SelectTrigger>
                <SelectContent>
                  {availableVersions.map(version => (
                    <SelectItem key={version.id} value={version.version_number}>
                      {version.version_number} - {version.version_name}
                      {version.is_active && <Badge className="ml-2">Active</Badge>}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="database-name">Database Name *</Label>
              <Select value={databaseName} onValueChange={setDatabaseName}>
                <SelectTrigger>
                  <SelectValue placeholder="Select database" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="FlexnetDB">FlexnetDB (MSSQL)</SelectItem>
                  <SelectItem value="AMDS">AMDS (PostgreSQL)</SelectItem>
                  <SelectItem value="Router">Router (PostgreSQL)</SelectItem>
                  <SelectItem value="FWDL">FWDL (PostgreSQL)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button 
            onClick={handleQueryAssistance} 
            disabled={loading || !rniVersion || !databaseName}
            className="w-full"
          >
            {loading ? (
              <>
                <Clock className="h-4 w-4 mr-2 animate-spin" />
                Checking Data Dictionary...
              </>
            ) : (
              <>
                <Search className="h-4 w-4 mr-2" />
                Get Query Assistance
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {queryResult && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {queryResult.status === 'data_dictionary_available' && <CheckCircle className="h-5 w-5 text-green-500" />}
              {queryResult.status === 'schema_extraction_needed' && <AlertTriangle className="h-5 w-5 text-yellow-500" />}
              {queryResult.status === 'database_not_configured' && <XCircle className="h-5 w-5 text-red-500" />}
              {queryResult.status === 'rni_version_not_found' && <XCircle className="h-5 w-5 text-red-500" />}
              Query Assistance Result
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="font-medium">Status: {queryResult.status?.replace('_', ' ')}</p>
              <p className="text-sm text-gray-600 mt-1">{queryResult.message}</p>
            </div>

            {queryResult.status === 'data_dictionary_available' && queryResult.schemas_available && (
              <div>
                <h4 className="font-medium mb-2">Available Schemas:</h4>
                <div className="space-y-2">
                  {queryResult.schemas_available.map((schema: any, index: number) => (
                    <div key={index} className="flex items-center justify-between p-2 bg-green-50 rounded">
                      <span className="font-medium">{schema.schema_name}</span>
                      <Badge variant="secondary">{schema.table_count} tables</Badge>
                    </div>
                  ))}
                </div>
                <p className="text-sm text-gray-600 mt-2">
                  Data dictionary is available. You can proceed with your queries using the schema information.
                </p>
              </div>
            )}

            {queryResult.status === 'schema_extraction_needed' && queryResult.extraction_query && (
              <div>
                <h4 className="font-medium mb-2">Schema Extraction Required</h4>
                <p className="text-sm text-gray-600 mb-3">
                  No schema information is available. Run the following query on your {queryResult.database_type} database to extract the schema:
                </p>
                
                <div className="bg-gray-900 text-gray-100 p-4 rounded-lg text-sm font-mono overflow-x-auto">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-gray-400">Extraction Query ({queryResult.database_type})</span>
                    <Button 
                      variant="outline" 
                      onClick={() => copyToClipboard(queryResult.extraction_query)}
                      className="h-6 px-2 text-xs"
                    >
                      Copy
                    </Button>
                  </div>
                  <pre className="whitespace-pre-wrap">{queryResult.extraction_query}</pre>
                </div>
                
                <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded">
                  <h5 className="font-medium text-blue-800">Next Steps:</h5>
                  <ol className="list-decimal list-inside text-sm text-blue-700 mt-1 space-y-1">
                    <li>Copy the extraction query above</li>
                    <li>Connect to your {databaseName} database server</li>
                    <li>Execute the query in your SQL client</li>
                    <li>Export the results as a CSV file</li>
                    <li>Upload the CSV file using the "Upload Schema" button</li>
                  </ol>
                  <p className="text-xs text-blue-600 mt-2">
                    <strong>Note:</strong> The system cannot access your database servers directly. You must run the query and upload the results manually.
                  </p>
                </div>
              </div>
            )}

            {queryResult.status === 'database_not_configured' && (
              <div className="p-3 bg-orange-50 border border-orange-200 rounded">
                <h5 className="font-medium text-orange-800">Database Not Configured</h5>
                <p className="text-sm text-orange-700 mt-1">
                  The database {databaseName} is not configured for RNI version {rniVersion}. 
                  Please add it using the "Database Instances" tab first.
                </p>
              </div>
            )}

            {queryResult.status === 'rni_version_not_found' && (
              <div className="p-3 bg-red-50 border border-red-200 rounded">
                <h5 className="font-medium text-red-800">RNI Version Not Found</h5>
                <p className="text-sm text-red-700 mt-1">
                  RNI version {rniVersion} was not found. Please check available versions in the dropdown.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Sensus AMI Databases</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 border rounded-lg">
              <h4 className="font-semibold text-blue-600">FlexnetDB (Microsoft SQL Server)</h4>
              <p className="text-sm text-gray-600 mt-1">
                Primary Sensus AMI database containing meter data, billing information, and infrastructure management.
              </p>
            </div>
            <div className="p-4 border rounded-lg">
              <h4 className="font-semibold text-green-600">AMDS (PostgreSQL)</h4>
              <p className="text-sm text-gray-600 mt-1">
                Advanced Metering Data System for real-time meter reading and data processing.
              </p>
            </div>
            <div className="p-4 border rounded-lg">
              <h4 className="font-semibold text-green-600">Router (PostgreSQL)</h4>
              <p className="text-sm text-gray-600 mt-1">
                Communication management database for AMI network routing and device connectivity.
              </p>
            </div>
            <div className="p-4 border rounded-lg">
              <h4 className="font-semibold text-green-600">FWDL (PostgreSQL)</h4>
              <p className="text-sm text-gray-600 mt-1">
                Firmware Download management system for device updates and version control.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}