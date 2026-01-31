"""
QA Regression Agent - Runs golden workflows and test suites

This agent is responsible for:
- Running golden workflows on demand
- Executing test suites
- Producing verification reports
- Comparing results against baselines
"""

import asyncio
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.qa_guardian.schemas.agent_schemas import RegressionInput, RegressionOutput
from backend.qa_guardian.schemas.proposal import VerificationReport, TestResult, WorkflowResult

logger = logging.getLogger("qa_guardian.agents.regression")


class QARegressionAgent:
    """
    QA Regression Agent
    
    Runs golden workflows and test suites to verify system health.
    
    Permission Boundaries:
    - CAN READ: Test files, workflow definitions, test results
    - CAN EXECUTE: pytest, golden workflow runners (read-only tests)
    - CANNOT: Modify code, access secrets, make external calls
    """
    
    AGENT_ID = "qa_regression_agent"
    DEPARTMENT = "qa_guardian"
    
    # Test file locations
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    TESTS_DIR = PROJECT_ROOT / "tests"
    GOLDEN_WORKFLOWS_DIR = TESTS_DIR / "golden_workflows"
    QA_TESTS_DIR = TESTS_DIR / "qa_guardian"
    
    # Golden workflow identifiers
    GOLDEN_WORKFLOWS = {
        "golden_core_task_flow": "TestGoldenCoreWorkflow",
        "golden_cmp_flow": "TestGoldenCMPWorkflow",
        "golden_tool_reliability": "TestGoldenToolReliability",
        "golden_memory_integrity": "TestGoldenMemoryWorkflow",
        "golden_qa_guardian": "TestGoldenQAGuardian"
    }
    
    def __init__(self):
        self.last_run: Optional[datetime] = None
        self.baseline_results: Dict[str, bool] = {}
    
    async def process(self, input: RegressionInput) -> RegressionOutput:
        """
        Run regression tests based on input parameters.
        
        Args:
            input: RegressionInput specifying what to run
            
        Returns:
            RegressionOutput with test results
        """
        start_time = datetime.utcnow()
        
        try:
            test_results = []
            workflow_results = []
            failed_tests = []
            failed_workflows = []
            
            # Determine what to run
            if input.run_type == "smoke":
                # Quick smoke tests only
                test_results = await self._run_smoke_tests(input.timeout_seconds)
                
            elif input.run_type == "golden_only":
                # Only golden workflows
                workflow_results = await self._run_golden_workflows(
                    input.specific_workflows or list(self.GOLDEN_WORKFLOWS.keys()),
                    input.timeout_seconds
                )
                
            elif input.run_type == "specific_tests":
                # Specific tests only
                test_results = await self._run_specific_tests(
                    input.specific_tests,
                    input.timeout_seconds,
                    input.stop_on_first_failure
                )
                
            elif input.run_type == "full":
                # Full suite
                test_results = await self._run_all_tests(input.timeout_seconds)
                workflow_results = await self._run_golden_workflows(
                    list(self.GOLDEN_WORKFLOWS.keys()),
                    input.timeout_seconds
                )
            
            # Calculate summary
            tests_passed = sum(1 for t in test_results if t.status == "passed")
            tests_failed = sum(1 for t in test_results if t.status == "failed")
            tests_skipped = sum(1 for t in test_results if t.status == "skipped")
            
            workflows_passed = sum(1 for w in workflow_results if w.status == "passed")
            workflows_failed = sum(1 for w in workflow_results if w.status == "failed")
            
            # Get failed items
            failed_tests = [t.test_name for t in test_results if t.status == "failed"]
            failed_workflows = [w.workflow_id for w in workflow_results if w.status == "failed"]
            
            # Compare to baseline to find new failures
            new_failures = self._find_new_failures(failed_tests)
            
            # Calculate pass rate
            total_tests = len(test_results)
            pass_rate = tests_passed / total_tests if total_tests > 0 else 0.0
            
            # All passed?
            all_passed = tests_failed == 0 and workflows_failed == 0
            
            exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Create verification report if for a proposal
            verification_report_id = None
            if input.proposal_id:
                report = VerificationReport(
                    proposal_id=input.proposal_id,
                    tests_run=total_tests,
                    tests_passed=tests_passed,
                    tests_failed=tests_failed,
                    tests_skipped=tests_skipped,
                    golden_workflows_run=len(workflow_results),
                    golden_workflows_passed=workflows_passed,
                    test_results=test_results,
                    workflow_results=workflow_results,
                    new_errors_detected=new_failures,
                    duration_ms=exec_time
                )
                report.evaluate_success()
                verification_report_id = report.report_id
            
            self.last_run = datetime.utcnow()
            
            return RegressionOutput(
                request_id=input.request_id,
                success=True,
                execution_time_ms=exec_time,
                total_tests=total_tests,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                tests_skipped=tests_skipped,
                total_workflows=len(workflow_results),
                workflows_passed=workflows_passed,
                workflows_failed=workflows_failed,
                all_passed=all_passed,
                pass_rate=pass_rate,
                failed_tests=failed_tests,
                failed_workflows=failed_workflows,
                new_failures=new_failures,
                verification_report_id=verification_report_id,
                duration_ms=exec_time
            )
            
        except Exception as e:
            logger.error(f"Regression agent error: {e}")
            return RegressionOutput(
                request_id=input.request_id,
                success=False,
                error=str(e),
                execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
            )
    
    async def _run_smoke_tests(self, timeout: int) -> List[TestResult]:
        """Run quick smoke tests"""
        return await self._run_pytest(
            [str(self.QA_TESTS_DIR), "-v", "--tb=short", "-x"],
            timeout
        )
    
    async def _run_golden_workflows(self, workflow_ids: List[str], 
                                     timeout: int) -> List[WorkflowResult]:
        """Run golden workflow tests"""
        results = []
        
        for workflow_id in workflow_ids:
            if workflow_id not in self.GOLDEN_WORKFLOWS:
                results.append(WorkflowResult(
                    workflow_id=workflow_id,
                    workflow_name=workflow_id,
                    status="error",
                    duration_ms=0,
                    steps_completed=0,
                    total_steps=1,
                    error_message=f"Unknown workflow: {workflow_id}"
                ))
                continue
            
            test_class = self.GOLDEN_WORKFLOWS[workflow_id]
            start = datetime.utcnow()
            
            try:
                # Run specific test class
                cmd = [
                    sys.executable, "-m", "pytest",
                    str(self.GOLDEN_WORKFLOWS_DIR / "test_golden_workflows.py"),
                    "-v", "--tb=short", f"-k{test_class}"
                ]
                
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=timeout
                    )
                    
                    duration = int((datetime.utcnow() - start).total_seconds() * 1000)
                    
                    if proc.returncode == 0:
                        results.append(WorkflowResult(
                            workflow_id=workflow_id,
                            workflow_name=test_class,
                            status="passed",
                            duration_ms=duration,
                            steps_completed=1,
                            total_steps=1
                        ))
                    else:
                        results.append(WorkflowResult(
                            workflow_id=workflow_id,
                            workflow_name=test_class,
                            status="failed",
                            duration_ms=duration,
                            steps_completed=0,
                            total_steps=1,
                            error_message=stderr.decode()[:500]
                        ))
                        
                except asyncio.TimeoutError:
                    results.append(WorkflowResult(
                        workflow_id=workflow_id,
                        workflow_name=test_class,
                        status="error",
                        duration_ms=timeout * 1000,
                        steps_completed=0,
                        total_steps=1,
                        error_message="Timeout"
                    ))
                    
            except Exception as e:
                results.append(WorkflowResult(
                    workflow_id=workflow_id,
                    workflow_name=test_class,
                    status="error",
                    duration_ms=0,
                    steps_completed=0,
                    total_steps=1,
                    error_message=str(e)
                ))
        
        return results
    
    async def _run_specific_tests(self, test_paths: List[str], timeout: int,
                                   stop_on_first: bool) -> List[TestResult]:
        """Run specific test files"""
        args = ["-v", "--tb=short"]
        if stop_on_first:
            args.append("-x")
        args.extend(test_paths)
        
        return await self._run_pytest(args, timeout)
    
    async def _run_all_tests(self, timeout: int) -> List[TestResult]:
        """Run all tests"""
        return await self._run_pytest(
            [str(self.TESTS_DIR), "-v", "--tb=short", 
             "--ignore=" + str(self.GOLDEN_WORKFLOWS_DIR)],
            timeout
        )
    
    async def _run_pytest(self, args: List[str], timeout: int) -> List[TestResult]:
        """Run pytest with given arguments and parse results"""
        results = []
        start = datetime.utcnow()
        
        try:
            cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q"] + args[:1]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=30
                )
                
                # Parse collected tests
                test_names = []
                for line in stdout.decode().split('\n'):
                    if '::' in line and line.strip():
                        test_names.append(line.strip())
                
                # Run actual tests
                run_cmd = [sys.executable, "-m", "pytest"] + args
                
                proc = await asyncio.create_subprocess_exec(
                    *run_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
                
                duration = int((datetime.utcnow() - start).total_seconds() * 1000)
                per_test_time = duration // max(1, len(test_names))
                
                # Parse results from output
                output = stdout.decode()
                
                for test_name in test_names:
                    short_name = test_name.split("::")[-1] if "::" in test_name else test_name
                    
                    if f"{short_name} PASSED" in output or "passed" in output.lower():
                        results.append(TestResult(
                            test_name=short_name,
                            file_path=args[0] if args else "unknown",
                            status="passed",
                            duration_ms=per_test_time
                        ))
                    elif f"{short_name} FAILED" in output:
                        results.append(TestResult(
                            test_name=short_name,
                            file_path=args[0] if args else "unknown",
                            status="failed",
                            duration_ms=per_test_time,
                            error_message="Test failed"
                        ))
                    else:
                        results.append(TestResult(
                            test_name=short_name,
                            file_path=args[0] if args else "unknown",
                            status="skipped",
                            duration_ms=0
                        ))
                
                # If no specific tests found, create summary result
                if not results:
                    if proc.returncode == 0:
                        results.append(TestResult(
                            test_name="test_suite",
                            file_path=args[0] if args else "unknown",
                            status="passed",
                            duration_ms=duration
                        ))
                    else:
                        results.append(TestResult(
                            test_name="test_suite",
                            file_path=args[0] if args else "unknown",
                            status="failed",
                            duration_ms=duration,
                            error_message=stderr.decode()[:500]
                        ))
                        
            except asyncio.TimeoutError:
                results.append(TestResult(
                    test_name="timeout",
                    file_path=args[0] if args else "unknown",
                    status="error",
                    duration_ms=timeout * 1000,
                    error_message="Test execution timed out"
                ))
                
        except Exception as e:
            logger.error(f"pytest execution error: {e}")
            results.append(TestResult(
                test_name="error",
                file_path="unknown",
                status="error",
                duration_ms=0,
                error_message=str(e)
            ))
        
        return results
    
    def _find_new_failures(self, failed_tests: List[str]) -> List[str]:
        """Find failures that are new (not in baseline)"""
        # For now, return all failures as new
        # TODO: Implement baseline comparison
        return failed_tests
    
    def update_baseline(self, test_results: List[TestResult]):
        """Update baseline with current passing tests"""
        for result in test_results:
            self.baseline_results[result.test_name] = (result.status == "passed")
