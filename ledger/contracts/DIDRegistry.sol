// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title DIDRegistry
 * @notice Anchors decentralized identifiers (DIDs) and credential revocation
 *         status on-chain for the Unified Digital Identity Management System.
 *         Identity documents themselves live off-chain (IPFS); only the
 *         owner, document hash, and revocation flags are stored on-chain.
 */
contract DIDRegistry {
    struct DIDDocument {
        address owner;
        bytes32 docHash;   // keccak256 of the off-chain DID document (IPFS CID content)
        uint256 updatedAt;
        bool exists;
        bool revoked;
    }

    mapping(string => DIDDocument) private _dids;
    mapping(bytes32 => bool) private _revokedCredentials; // credential hash => revoked
    mapping(address => bool) public trustedIssuers;

    string[] private _didList;

    event DIDCreated(string indexed didId, address indexed owner, bytes32 docHash);
    event DIDUpdated(string indexed didId, bytes32 newDocHash);
    event DIDRevoked(string indexed didId, address indexed revokedBy);
    event IssuerAdded(address indexed issuer);
    event IssuerRemoved(address indexed issuer);
    event CredentialRevoked(bytes32 indexed credentialHash, address indexed revokedBy);

    modifier onlyOwner(string memory didId) {
        require(_dids[didId].owner == msg.sender, "DIDRegistry: caller is not the DID owner");
        _;
    }

    modifier onlyTrustedIssuer() {
        require(trustedIssuers[msg.sender], "DIDRegistry: caller is not a trusted issuer");
        _;
    }

    constructor() {
        trustedIssuers[msg.sender] = true; // deployer is the first trusted issuer
        emit IssuerAdded(msg.sender);
    }

    function createDID(string calldata didId, bytes32 docHash) external {
        require(!_dids[didId].exists, "DIDRegistry: DID already exists");
        require(msg.sender != address(0), "DIDRegistry: invalid owner");
        _dids[didId] = DIDDocument({
            owner: msg.sender,
            docHash: docHash,
            updatedAt: block.timestamp,
            exists: true,
            revoked: false
        });
        _didList.push(didId);
        emit DIDCreated(didId, msg.sender, docHash);
    }

    function updateDID(string calldata didId, bytes32 newDocHash)
        external onlyOwner(didId)
    {
        require(!_dids[didId].revoked, "DIDRegistry: DID is revoked");
        _dids[didId].docHash = newDocHash;
        _dids[didId].updatedAt = block.timestamp;
        emit DIDUpdated(didId, newDocHash);
    }

    function revokeDID(string calldata didId) external onlyOwner(didId) {
        _dids[didId].revoked = true;
        emit DIDRevoked(didId, msg.sender);
    }

    /// @notice Trusted issuers (or governance) revoke a leaked/fraudulent credential.
    function revokeCredential(bytes32 credentialHash) external onlyTrustedIssuer {
        _revokedCredentials[credentialHash] = true;
        emit CredentialRevoked(credentialHash, msg.sender);
    }

    function addIssuer(address issuer) external onlyTrustedIssuer {
        trustedIssuers[issuer] = true;
        emit IssuerAdded(issuer);
    }

    // ---------- view helpers ----------

    function resolveDID(string calldata didId)
        external view
        returns (address owner, bytes32 docHash, uint256 updatedAt, bool revoked)
    {
        require(_dids[didId].exists, "DIDRegistry: DID not found");
        DIDDocument memory d = _dids[didId];
        return (d.owner, d.docHash, d.updatedAt, d.revoked);
    }

    function isCredentialRevoked(bytes32 credentialHash) external view returns (bool) {
        return _revokedCredentials[credentialHash];
    }

    function totalDIDs() external view returns (uint256) {
        return _didList.length;
    }
}
