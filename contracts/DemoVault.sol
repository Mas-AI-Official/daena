// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * DemoVault - A vulnerable smart contract for Daena demo
 * 
 * This contract intentionally contains common vulnerabilities to demonstrate
 * Daena's DeFi security scanning capabilities.
 * 
 * VULNERABILITIES (for demo):
 * 1. Reentrancy in withdraw function
 * 2. Missing access control
 * 3. Unchecked return values
 * 4. Integer overflow potential (pre-0.8)
 */

contract DemoVault {
    mapping(address => uint256) public balances;
    address public owner;
    
    event Deposit(address indexed user, uint256 amount);
    event Withdrawal(address indexed user, uint256 amount);
    
    constructor() {
        owner = msg.sender;
    }
    
    /**
     * Deposit ETH into the vault
     */
    function deposit() external payable {
        require(msg.value > 0, "Must deposit something");
        balances[msg.sender] += msg.value;
        emit Deposit(msg.sender, msg.value);
    }
    
    /**
     * VULNERABLE: Reentrancy attack possible here
     * The external call happens before balance update
     */
    function withdraw() external {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "No balance");
        
        // VULNERABILITY: External call before state update
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");
        
        // State update happens after external call
        // An attacker can re-enter before balance is zeroed
        balances[msg.sender] = 0;
        
        emit Withdrawal(msg.sender, amount);
    }
    
    /**
     * Emergency withdrawal for owner
     * VULNERABILITY: No access modifier - anyone can call
     */
    function emergencyWithdraw() external {
        // Should check: require(msg.sender == owner, "Not owner");
        payable(msg.sender).transfer(address(this).balance);
    }
    
    /**
     * Update owner
     * VULNERABILITY: Missing ownership check
     */
    function setOwner(address newOwner) external {
        // Anyone can change the owner!
        owner = newOwner;
    }
    
    /**
     * Get contract balance
     */
    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }
    
    /**
     * Get user balance
     */
    function getUserBalance(address user) external view returns (uint256) {
        return balances[user];
    }
}
