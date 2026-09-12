// ledger/scripts/deploy.js - deploy DIDRegistry and print the address
const hre = require("hardhat");

async function main() {
  const Factory = await hre.ethers.getContractFactory("DIDRegistry");
  const contract = await Factory.deploy();
  await contract.waitForDeployment();
  const address = await contract.getAddress();
  console.log("DIDRegistry deployed to:", address);
  console.log("Set this as LEDGER_CONTRACT_ADDRESS for the API.");
}

main().catch((err) => { console.error(err); process.exit(1); });
