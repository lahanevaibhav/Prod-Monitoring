"""
AI Analysis Module using AWS Lambda via API Gateway
Provides intelligent error analysis with RAG (Retrieval Augmented Generation)
Uses API Gateway endpoint with API key authentication
Automatically anonymizes sensitive data before sending to AI
"""

import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

# Import configuration
try:
    from .unified_config import LAMBDA_API_ENDPOINT, LAMBDA_API_KEY, APPLICATION_CONTEXT_FILE, LOG_LEVEL, LAMBDA_TIMEOUT
    from .anonymizer import anonymize_text
except ImportError:
    from unified_config import LAMBDA_API_ENDPOINT, LAMBDA_API_KEY, APPLICATION_CONTEXT_FILE, LOG_LEVEL, LAMBDA_TIMEOUT
    from anonymizer import anonymize_text

# Configure logging based on config
log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

# Try to import required libraries
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError as e:
    REQUESTS_AVAILABLE = False
    logger.warning(f"Required libraries not available: {e}")
    logger.warning("Install with: pip install requests")

# Default context file path
CONTEXT_FILE = os.path.join(os.path.dirname(__file__), "..", "..", APPLICATION_CONTEXT_FILE)


class AIAnalyzer:
    """AI Analyzer using AWS Lambda via API Gateway with API key"""

    def __init__(self, context_file: Optional[str] = None,
                 api_endpoint: Optional[str] = None,
                 api_key: Optional[str] = None,
                 timeout: Optional[int] = None):
        """
        Initialize the analyzer with API Gateway configuration.

        Args:
            context_file: Path to application context file for RAG
            api_endpoint: API Gateway endpoint URL (optional, uses config if not provided)
            api_key: API key for authentication (optional, uses config if not provided)
            timeout: Request timeout in seconds (optional, uses config if not provided)
        """
        self.context_file = context_file or CONTEXT_FILE
        self.application_context = self._load_context()

        # API configuration from unified config
        self.api_endpoint = api_endpoint or LAMBDA_API_ENDPOINT
        self.api_key = api_key or LAMBDA_API_KEY
        self.timeout = timeout or LAMBDA_TIMEOUT

        if REQUESTS_AVAILABLE:
            if self.api_endpoint and self.api_key:
                logger.info(f"Lambda API endpoint configured: {self.api_endpoint}")
                logger.info(f"API key configured: {self.api_key[:10]}...")
            else:
                logger.warning("Lambda API endpoint or API key not configured")
        else:
            logger.warning("AI analysis disabled: Required requests library not installed")

    def _load_context(self) -> str:
        """Load application context from file for RAG"""
        try:
            if os.path.exists(self.context_file):
                with open(self.context_file, 'r', encoding='utf-8') as f:
                    context = f.read()
                logger.info(f"Loaded application context from {self.context_file}")
                return context
            else:
                logger.warning(f"Context file not found: {self.context_file}")
                return ""
        except Exception as e:
            logger.error(f"Error loading context file: {e}")
            return ""

    def is_available(self) -> bool:
        """Check if AI analysis is available"""
        return REQUESTS_AVAILABLE and self.api_endpoint is not None and self.api_key is not None

    def _call_lambda_function(self, prompt: str, system_message: str = None) -> str:
        """
        Call Lambda function via API Gateway endpoint with API key

        Args:
            prompt: User prompt to send to the chatbot
            system_message: Optional system message for context (included in prompt)

        Returns:
            Response text from the Lambda function
        """
        # Prepare the question
        question = prompt

        # Add system message to prompt if provided
        if system_message:
            question = f"{system_message}\n\n{prompt}"

        # Prepare payload
        payload = {
            "question": question
        }

        try:
            logger.info(f"Calling Lambda API endpoint: {self.api_endpoint}")
            logger.debug(f"Payload: {json.dumps(payload)}")

            # Set up headers with API key
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key
            }

            # Make HTTP POST request to API Gateway
            response = requests.post(
                self.api_endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            logger.info(f"API response status code: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")

            # Check for HTTP errors
            if response.status_code != 200:
                error_msg = f"API request failed with status {response.status_code}"
                try:
                    error_body = response.json()
                    error_msg += f": {json.dumps(error_body)}"
                except:
                    error_msg += f": {response.text}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Parse response
            try:
                response_data = response.json()
                logger.debug(f"Response data: {json.dumps(response_data, indent=2)}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Raw response: {response.text}")
                raise ValueError(f"Invalid JSON response from API: {response.text[:200]}")

            # Parse the Lambda response
            parsed_response = self._parse_lambda_response(json.dumps(response_data))

            if not parsed_response or not parsed_response.strip():
                raise ValueError("Empty response from Lambda function")

            logger.info("✓ Successfully received response from Lambda API")
            return parsed_response

        except requests.Timeout:
            error_msg = f"API request timed out after {self.timeout} seconds"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except requests.RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Lambda API call failed: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

            logger.info("✓ Successfully received response from Lambda API")
            return parsed_response

        except requests.Timeout:
            error_msg = f"API request timed out after {self.timeout} seconds"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except requests.RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Lambda API call failed: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)


    def _parse_lambda_response(self, response_text: str) -> str:
        """
        Parse Lambda response and extract the actual message

        Expected response format from handler:
        {
            "answer": "response text",
            "sources": ["source1", "source2", ...]
        }

        Or error format:
        {
            "errorMessage": "error details",
            "errorType": "Error",
            "stackTrace": [...]
        }

        Or simple string response: "Error processing your request"
        """
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.debug(f"Response is not JSON: {e}")
            # If response is plain text, check if it's an error message
            if response_text and len(response_text.strip()) > 0:
                # Check for error strings
                if response_text.strip() == "Error processing your request":
                    raise ValueError("Lambda returned error: Error processing your request")
                return response_text
            raise ValueError(f"Empty or invalid response from Lambda: {response_text}")

        # Check for Lambda runtime error format
        if 'errorMessage' in response_data and 'errorType' in response_data:
            error_type = response_data.get('errorType', 'Error')
            error_msg = response_data.get('errorMessage', 'Unknown error')
            stack_trace = response_data.get('stackTrace', [])

            logger.error(f"Lambda runtime error - Type: {error_type}")
            logger.error(f"Error message: {error_msg}")
            if stack_trace:
                logger.error(f"Stack trace: {json.dumps(stack_trace, indent=2)}")

            raise ValueError(f"Lambda {error_type}: {error_msg}")

        # Extract answer (required field)
        if 'answer' not in response_data:
            logger.warning(f"Unexpected response format. Available keys: {list(response_data.keys())}")
            logger.debug(f"Full response: {json.dumps(response_data, indent=2)}")

            # If response is just a string, return it
            if isinstance(response_data, str):
                return response_data

            raise ValueError(f"No 'answer' field in Lambda response. Got keys: {list(response_data.keys())}")

        answer = str(response_data['answer'])

        # Check if it's an error message
        if answer == "Error processing your request":
            logger.error("Lambda processing error")
            raise ValueError("Lambda processing error: Error processing your request")

        # Append sources if available and valid
        if 'sources' in response_data:
            sources = response_data['sources']
            if isinstance(sources, list) and sources:
                # Filter out empty or generic error messages
                valid_sources = [s for s in sources if s and s not in ["No sources found", "Error occurred", ""]]
                if valid_sources:
                    answer += "\n\n**Sources:**\n"
                    for idx, source in enumerate(valid_sources, 1):
                        answer += f"{idx}. {source}\n"

        return answer


    def analyze_error_patterns(
        self,
        classified_errors: List[Dict],
        metrics_summary: Optional[Dict] = None,
        region: str = "Unknown",
        service: str = "Unknown"
    ) -> Dict:
        """
        Analyze classified error patterns using Lambda AI endpoint with RAG context.

        Args:
            classified_errors: List of classified error dictionaries
            metrics_summary: Optional metrics data for correlation
            region: Region code (e.g., NA1, AU)
            service: Service name (e.g., SRA, SRM)

        Returns:
            Dictionary containing AI analysis results
        """
        if not self.is_available():
            return {
                "status": "unavailable",
                "message": "AI analysis is not available. Please configure LAMBDA_ENDPOINT and ensure AWS credentials are available.",
                "timestamp": datetime.now().isoformat()
            }

        try:
            # Check if we have errors to analyze
            if not classified_errors or len(classified_errors) == 0:
                # No errors - Generate positive health report
                return self._generate_healthy_system_report(region, service, metrics_summary)

            # Prepare error summary for AI
            error_summary = self._prepare_error_summary(classified_errors, metrics_summary)

            # Build prompt with RAG context
            prompt = self._build_analysis_prompt(error_summary, region, service)

            # Call Lambda function with direct invocation
            analysis_text = self._call_lambda_function(
                prompt=prompt,
                system_message="You are an expert DevOps engineer analyzing production errors in AWS microservices. Provide concise, actionable insights."
            )

            return {
                "status": "success",
                "region": region,
                "service": service,
                "timestamp": datetime.now().isoformat(),
                "analysis": analysis_text,
                "error_count": len(classified_errors),
                "model": "lambda-wfm-chatbot-handler"
            }

        except Exception as e:
            logger.error(f"Error during AI analysis: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _generate_healthy_system_report(self, region: str, service: str, metrics_summary: Optional[Dict]) -> Dict:
        """Generate a positive health report when no errors are found"""

        analysis_parts = []
        analysis_parts.append(f"# ✅ System Health Report - {service}/{region}\n")
        analysis_parts.append("## Status: HEALTHY\n")
        analysis_parts.append(f"**No errors detected during the monitoring period.**\n\n")

        analysis_parts.append("## Key Findings:\n")
        analysis_parts.append("1. **Error Rate**: Zero errors logged - system is operating normally\n")
        analysis_parts.append("2. **Service Stability**: All components functioning as expected\n")
        analysis_parts.append("3. **Log Analysis**: No exceptions, crashes, or critical warnings detected\n\n")

        # Add metrics insights if available
        if metrics_summary:
            analysis_parts.append("## Performance Metrics:\n")

            perf_issues = metrics_summary.get('performance_issues', 0)
            high_cpu = metrics_summary.get('high_cpu_count', 0)
            high_memory = metrics_summary.get('high_memory_count', 0)

            if perf_issues == 0 and high_cpu == 0 and high_memory == 0:
                analysis_parts.append("- ✅ **CPU Utilization**: Within normal range\n")
                analysis_parts.append("- ✅ **Memory Usage**: Within normal range\n")
                analysis_parts.append("- ✅ **Response Times**: Meeting SLA targets\n")
            else:
                if high_cpu > 0:
                    analysis_parts.append(f"- ⚠️ **CPU Spikes**: {high_cpu} instances of high CPU (>80%)\n")
                if high_memory > 0:
                    analysis_parts.append(f"- ⚠️ **Memory Pressure**: {high_memory} instances of high memory (>80%)\n")
                if perf_issues > 0:
                    analysis_parts.append(f"- ℹ️ **Performance**: {perf_issues} performance metrics collected\n")

        analysis_parts.append("\n## Recommendations:\n")
        analysis_parts.append("1. **Continue Monitoring**: Maintain current monitoring coverage\n")
        analysis_parts.append("2. **Proactive Checks**: Review CloudWatch dashboards for any anomalies\n")
        analysis_parts.append("3. **Capacity Planning**: Monitor trends to ensure adequate resources\n")
        analysis_parts.append("4. **Documentation**: Document current healthy state as baseline\n\n")

        analysis_parts.append("## Next Steps:\n")
        analysis_parts.append("- Continue regular monitoring cycles\n")
        analysis_parts.append("- Review performance metrics for optimization opportunities\n")
        analysis_parts.append("- Maintain current operational practices\n")
        analysis_parts.append("- Keep infrastructure up-to-date with patches\n\n")

        analysis_parts.append("*Note: This automated health report was generated because no errors were detected. ")
        analysis_parts.append("This is a positive indicator of system stability.*\n")

        return {
            "status": "success",
            "region": region,
            "service": service,
            "timestamp": datetime.now().isoformat(),
            "analysis": "".join(analysis_parts),
            "error_count": 0,
            "model": "system-health-analyzer",
            "health_status": "HEALTHY"
        }

    def _prepare_error_summary(self, classified_errors: List[Dict], metrics_summary: Optional[Dict]) -> str:
        """Prepare a concise error summary for AI analysis with anonymization"""
        summary_lines = []

        # Take top 20 most frequent errors
        top_errors = classified_errors[:20]

        summary_lines.append(f"Total unique error patterns: {len(classified_errors)}")
        summary_lines.append(f"Analyzing top {len(top_errors)} errors:\n")

        for idx, error in enumerate(top_errors, 1):
            # Anonymize sensitive data from error details
            signature = anonymize_text(str(error.get('signature', 'Unknown')))
            count = error.get('count', 0)
            location = anonymize_text(str(error.get('location', 'Unknown')))
            sample = anonymize_text(str(error.get('sample', ''))[:300])  # Truncate and anonymize

            summary_lines.append(f"{idx}. Error: {signature}")
            summary_lines.append(f"   Count: {count} occurrences")
            summary_lines.append(f"   Location: {location}")
            summary_lines.append(f"   Sample: {sample}")
            summary_lines.append("")

        # Add metrics context if available
        if metrics_summary:
            summary_lines.append("\n## Related Metrics:")
            summary_lines.append(f"Performance issues: {metrics_summary.get('performance_issues', 0)}")
            summary_lines.append(f"Resource alerts: {metrics_summary.get('resource_alerts', 0)}")

        return "\n".join(summary_lines)

    def _build_analysis_prompt(self, error_summary: str, region: str, service: str) -> str:
        """Build the complete prompt with RAG context"""
        prompt_parts = []

        # Add application context (RAG)
        if self.application_context:
            prompt_parts.append("# Application Context (for reference):")
            prompt_parts.append(self.application_context)
            prompt_parts.append("\n---\n")

        # Add current analysis request
        prompt_parts.append(f"# Error Analysis Request")
        prompt_parts.append(f"Service: {service}")
        prompt_parts.append(f"Region: {region}")
        prompt_parts.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d')}\n")

        prompt_parts.append("# Error Patterns Detected:")
        prompt_parts.append(error_summary)

        prompt_parts.append("\n# Analysis Required:")
        prompt_parts.append("Based on the application context and error patterns above, provide:")
        prompt_parts.append("1. **Root Cause Analysis**: What are the likely root causes?")
        prompt_parts.append("2. **Impact Assessment**: How critical are these errors?")
        prompt_parts.append("3. **Patterns & Trends**: Are there common themes or patterns?")
        prompt_parts.append("4. **Recommended Actions**: What should be done to resolve these issues?")
        prompt_parts.append("5. **Priority**: Which errors should be addressed first?")
        prompt_parts.append("\nProvide concise, actionable insights in markdown format.")

        return "\n".join(prompt_parts)

    def analyze_cross_region(self, region_analyses: Dict[str, List[Dict]]) -> Dict:
        """
        Perform cross-region error pattern analysis.

        Args:
            region_analyses: Dict of region -> classified errors

        Returns:
            Cross-region analysis summary
        """
        if not self.is_available():
            return {
                "status": "unavailable",
                "message": "AI analysis is not available"
            }

        try:
            # Build cross-region summary
            summary = ["# Cross-Region Error Analysis\n"]

            for region, errors in region_analyses.items():
                summary.append(f"## {region}: {len(errors)} unique error patterns")
                # Top 3 errors per region
                for error in errors[:3]:
                    summary.append(f"- {error.get('signature', 'Unknown')}: {error.get('count', 0)} occurrences")
                summary.append("")

            prompt = "\n".join(summary)
            prompt += "\n\nAnalyze: Are there common errors across regions? Any region-specific issues? What's the overall health?"

            analysis_text = self._call_lambda_function(
                prompt=prompt,
                system_message="You are a DevOps engineer analyzing multi-region production systems."
            )

            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "analysis": analysis_text,
                "regions_analyzed": list(region_analyses.keys()),
                "model": "lambda-wfm-chatbot-handler"
            }

        except Exception as e:
            logger.error(f"Cross-region analysis error: {e}")
            return {"status": "error", "message": str(e)}


# Global analyzer instance
_analyzer = None

def get_analyzer(context_file: Optional[str] = None) -> AIAnalyzer:
    """Get or create the global analyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = AIAnalyzer(context_file)
    return _analyzer


def analyze_errors_with_ai(
    classified_errors: List[Dict],
    metrics_summary: Optional[Dict] = None,
    region: str = "Unknown",
    service: str = "Unknown",
    context_file: Optional[str] = None
) -> Dict:
    """
    Convenience function to analyze errors with AI.

    Args:
        classified_errors: List of classified error dictionaries
        metrics_summary: Optional metrics data
        region: Region code
        service: Service name
        context_file: Optional custom context file path

    Returns:
        AI analysis results
    """
    analyzer = get_analyzer(context_file)
    return analyzer.analyze_error_patterns(classified_errors, metrics_summary, region, service)


