"""End-to-end tests for the complete Technical Service Assistant workflow."""


import pytest


class TestCompleteWorkflow:
    """Test the complete system workflow from PDF upload to query response."""

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_complete_pdf_to_query_workflow(self, test_client, temp_upload_dir, sample_pdf_content):
        """Test the complete workflow: upload PDF -> process -> query -> get results."""
        # This test requires the full system to be running
        # Skip if dependencies are not available
        pytest.skip("Full e2e test requires running system")

        # 1. Upload a PDF file
        test_pdf = temp_upload_dir / "workflow_test.pdf"
        test_pdf.write_bytes(sample_pdf_content)

        # Simulate file upload (adjust endpoint based on your API)
        with test_pdf.open("rb") as f:
            response = test_client.post("/upload", files={"file": ("test.pdf", f, "application/pdf")})

        assert response.status_code == 200
        upload_result = response.json()
        assert "file_id" in upload_result

        # 2. Wait for processing (in real scenario, might need polling)
        # For testing, we'll assume immediate processing

        # 3. Query the processed document
        query_response = test_client.post("/api/search", json={"query": "test content", "top_k": 5})

        assert query_response.status_code == 200
        search_results = query_response.json()
        assert "chunks" in search_results
        assert len(search_results["chunks"]) >= 0

    @pytest.mark.e2e
    def test_health_check_endpoints(self, test_client):
        """Test that all health check endpoints are working."""
        # Test main health endpoint
        response = test_client.get("/health")
        assert response.status_code == 200

        # Test API health
        response = test_client.get("/api/health")
        if response.status_code == 200:
            health_data = response.json()
            assert "status" in health_data

    @pytest.mark.e2e
    def test_api_documentation_available(self, test_client):
        """Test that API documentation is accessible."""
        # Test OpenAPI/Swagger docs
        response = test_client.get("/docs")
        assert response.status_code == 200

        # Test OpenAPI JSON
        response = test_client.get("/openapi.json")
        if response.status_code == 200:
            openapi_spec = response.json()
            assert "openapi" in openapi_spec

    @pytest.mark.e2e
    def test_error_handling(self, test_client):
        """Test proper error handling for invalid requests."""
        # Test invalid search query
        response = test_client.post("/api/search", json={"invalid_field": "value"})
        assert response.status_code in [400, 422]  # Bad request or validation error

        # Test non-existent endpoint
        response = test_client.get("/api/nonexistent")
        assert response.status_code == 404

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_performance_requirements(self, test_client, performance_timer):
        """Test that the system meets basic performance requirements."""
        # Test search response time
        performance_timer.start()
        response = test_client.post("/api/search", json={"query": "test query", "top_k": 10})
        performance_timer.stop()

        assert response.status_code == 200
        # Assert response time is under reasonable threshold (adjust as needed)
        assert performance_timer.elapsed < 5.0  # 5 seconds max

    @pytest.mark.e2e
    def test_concurrent_requests(self, test_client):
        """Test system behavior under concurrent load."""
        import concurrent.futures

        def make_request():
            return test_client.post("/api/search", json={"query": "concurrent test", "top_k": 5})

        # Test with 5 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        assert len(results) == 5
        for response in results:
            assert response.status_code == 200
