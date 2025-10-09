'use client'

import TempUpload from '@/components/TempUpload'

export default function TempAnalysisPage() {
  const handleFileUploaded = (file: any) => {
    console.log('File uploaded:', file)
  }

  const handleAnalysisResult = (result: any) => {
    console.log('Analysis result:', result)
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h1 className="text-3xl font-bold text-gray-900">
            Document Analysis Tool
          </h1>
          <p className="mt-4 text-lg text-gray-600">
            Upload logs, configuration files, query results, or technical documents for immediate AI-powered analysis
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-8">
          <TempUpload 
            onFileUploaded={handleFileUploaded}
            onAnalysisResult={handleAnalysisResult}
          />
        </div>

        <div className="mt-8 bg-blue-50 rounded-lg p-6">
          <h2 className="text-lg font-medium text-blue-900 mb-3">
            Perfect for Troubleshooting
          </h2>
          <div className="grid md:grid-cols-2 gap-4 text-sm text-blue-800">
            <div>
              <h3 className="font-medium mb-2">Supported File Types:</h3>
              <ul className="space-y-1">
                <li>• Log files (.log, .out, .err, .trace)</li>
                <li>• Configuration files (.conf, .config, .ini)</li>
                <li>• Query results (.csv, .json, .sql)</li>
                <li>• Technical documents (.pdf, .txt)</li>
              </ul>
            </div>
            <div>
              <h3 className="font-medium mb-2">Use Cases:</h3>
              <ul className="space-y-1">
                <li>• Analyze error logs for root causes</li>
                <li>• Review configuration settings</li>
                <li>• Examine database query results</li>
                <li>• Extract insights from technical docs</li>
              </ul>
            </div>
          </div>
          <div className="mt-4 p-3 bg-blue-100 rounded text-sm text-blue-800">
            <strong>Privacy Note:</strong> Files are processed temporarily and automatically deleted after 2 hours. 
            No data is permanently stored.
          </div>
        </div>
      </div>
    </div>
  )
}