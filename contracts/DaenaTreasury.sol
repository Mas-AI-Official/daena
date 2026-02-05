// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

/**
 * @title DaenaTreasury
 * @dev Governance-controlled treasury for the Daena protocol.
 * Manages $DAENA reserves and provides a secure interface for operational spending.
 */
contract DaenaTreasury {
    address public governance;
    IERC20 public daenaToken;
    
    event FundsReleased(address indexed to, uint256 amount, string reason);
    event GovernanceUpdated(address indexed oldGov, address indexed newGov);

    modifier onlyGovernance() {
        require(msg.sender == governance, "Treasury: Caller is not governance");
        _;
    }

    constructor(address _daenaToken) {
        governance = msg.sender;
        daenaToken = IERC20(_daenaToken);
    }

    function transferGovernance(address newGovernance) public onlyGovernance {
        require(newGovernance != address(0), "Treasury: New governance is zero address");
        emit GovernanceUpdated(governance, newGovernance);
        governance = newGovernance;
    }

    /**
     * @dev Release DAENA tokens for operational use.
     * In the Daena ecosystem, this is triggered by the GovernanceLoop backend service
     * after a CRITICAL vote or Founder Approval.
     */
    function releaseFunds(address to, uint256 amount, string memory reason) public onlyGovernance {
        require(daenaToken.balanceOf(address(this)) >= amount, "Treasury: Insufficient balance");
        daenaToken.transfer(to, amount);
        emit FundsReleased(to, amount, reason);
    }

    function getBalance() public view returns (uint256) {
        return daenaToken.balanceOf(address(this));
    }
    
    // Fallback to receive ETH
    receive() external payable {}
}
