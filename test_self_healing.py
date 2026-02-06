import asyncio
import os
from backend.services.self_healing import get_self_healing_service
from backend.services.governance_loop import get_governance_loop

async def test_self_healing():
    healing = get_self_healing_service()
    gov = get_governance_loop()
    
    # 1. Propose a fix for a dummy file
    test_file = "test_fix_me.txt"
    with open(test_file, "w") as f:
        f.write("Original content")
    
    print(f"--- Proposing fix for {test_file} ---")
    proposal = await healing.propose_fix(
        file_path=test_file,
        proposed_code="Fixed content",
        rationale="Testing self-healing loop"
    )
    
    print(f"Proposal result: {proposal}")
    decision_id = proposal["decision_id"]
    
    # 2. Check pending
    pending = gov.get_pending()
    print(f"Pending approvals: {len(pending)}")
    
    # 3. Approve the fix
    print(f"--- Approving fix {decision_id} ---")
    gov.approve(decision_id, "founder", "Test approval")
    
    # 4. Apply the fix
    print(f"--- Applying fix {decision_id} ---")
    result = await healing.apply_fix(decision_id)
    print(f"Apply result: {result}")
    
    # 5. Verify the file
    with open(test_file, "r") as f:
        content = f.read()
    print(f"File content: {content}")
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)
    if os.path.exists(test_file + ".bak"):
        # find the bak file with wildcard
        import glob
        for bak in glob.glob(test_file + ".bak.*"):
            os.remove(bak)

if __name__ == "__main__":
    asyncio.run(test_self_healing())
