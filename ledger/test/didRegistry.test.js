const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("DIDRegistry", function () {
  let registry, owner, other, issuer2;

  beforeEach(async function () {
    [owner, other, issuer2] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("DIDRegistry");
    registry = await Factory.deploy();
    await registry.waitForDeployment();
  });

  it("creates and resolves a DID", async function () {
    const docHash = ethers.id("doc-v1");
    await registry.connect(other).createDID("did:ethr:unified:abc", docHash);
    const [resolvedOwner, hash, , revoked] = await registry.resolveDID("did:ethr:unified:abc");
    expect(resolvedOwner).to.equal(other.address);
    expect(hash).to.equal(docHash);
    expect(revoked).to.equal(false);
  });

  it("rejects duplicate DIDs", async function () {
    await registry.connect(other).createDID("did:ethr:unified:dup", ethers.id("d"));
    await expect(
      registry.connect(other).createDID("did:ethr:unified:dup", ethers.id("d2"))
    ).to.be.revertedWith("DIDRegistry: DID already exists");
  });

  it("only the owner updates the document", async function () {
    await registry.connect(other).createDID("did:ethr:unified:own", ethers.id("v1"));
    await registry.connect(other).updateDID("did:ethr:unified:own", ethers.id("v2"));
    await expect(
      registry.connect(owner).updateDID("did:ethr:unified:own", ethers.id("v3"))
    ).to.be.revertedWith("DIDRegistry: caller is not the DID owner");
  });

  it("trusted issuer revokes a credential and checks show revoked", async function () {
    const credHash = ethers.id("credential-xyz");
    await registry.revokeCredential(credHash); // deployer is trusted issuer
    expect(await registry.isCredentialRevoked(credHash)).to.equal(true);
    await registry.connect(issuer2).addIssuer(issuer2.address).catch(() => {});
  });

  it("non-issuer cannot revoke credentials", async function () {
    await expect(
      registry.connect(other).revokeCredential(ethers.id("c2"))
    ).to.be.revertedWith("DIDRegistry: caller is not a trusted issuer");
  });

  it("counts total DIDs", async function () {
    const before = await registry.totalDIDs();
    await registry.connect(other).createDID("did:ethr:unified:count", ethers.id("d"));
    expect(await registry.totalDIDs()).to.equal(Number(before) + 1);
  });
});
