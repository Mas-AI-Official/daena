// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title DaenaAgentNFT
 * @dev NFT representation of Daena Agents.
 * Each NFT stores traits, department affiliation, and reputation/skill level.
 */
contract DaenaAgentNFT {
    string public name = "Daena Autonomous Agent";
    string public symbol = "DAENA-AGENT";
    
    mapping(uint256 => address) private _owners;
    mapping(address => uint256) private _balances;
    mapping(uint256 => string) private _tokenURIs;
    
    struct AgentMeta {
        string name;
        string department;
        uint256 version;
        uint256 createdAt;
    }
    
    mapping(uint256 => AgentMeta) public agentMetadata;
    uint256 private _nextTokenId = 1;

    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);

    function mint(address to, string memory agentName, string memory department, string memory uri) public returns (uint256) {
        uint256 tokenId = _nextTokenId++;
        
        _owners[tokenId] = to;
        _balances[to] += 1;
        _tokenURIs[tokenId] = uri;
        
        agentMetadata[tokenId] = AgentMeta({
            name: agentName,
            department: department,
            version: 1,
            createdAt: block.timestamp
        });
        
        emit Transfer(address(0), to, tokenId);
        return tokenId;
    }

    function ownerOf(uint256 tokenId) public view returns (address) {
        address owner = _owners[tokenId];
        require(owner != address(0), "ERC721: invalid token ID");
        return owner;
    }

    function balanceOf(address owner) public view returns (uint256) {
        require(owner != address(0), "ERC721: address zero is not a valid owner");
        return _balances[owner];
    }
    
    function tokenURI(uint256 tokenId) public view returns (string memory) {
        require(_owners[tokenId] != address(0), "ERC721: invalid token ID");
        return _tokenURIs[tokenId];
    }
}
