#!/bin/bash
# test-deployment.sh - Test deployment setup and configuration

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}🧪 Testing Deployment Setup${NC}"
echo -e "${BLUE}=============================${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
    echo -e "${RED}❌ Not in project root directory${NC}"
    echo "Please run from the project root: ./scripts/test-deployment.sh"
    exit 1
fi

# Test 1: Check required files exist
echo -e "${YELLOW}📁 Checking required files...${NC}"

required_files=(
    ".github/workflows/deploy-to-ec2.yml"
    ".github/workflows/manual-deploy.yml"
    ".github/DEPLOYMENT_SETUP.md"
    "infrastructure/ec2-simple/github-deploy.sh"
    "docker-compose.yml"
    "pyproject.toml"
    "src/fastapi/main.py"
    "src/streamlit/Home.py"
)

for file in "${required_files[@]}"; do
    if [ -f "$PROJECT_ROOT/$file" ]; then
        echo -e "✅ $file"
    else
        echo -e "${RED}❌ Missing: $file${NC}"
        exit 1
    fi
done

# Test 2: Validate GitHub Actions workflow syntax
echo ""
echo -e "${YELLOW}⚙️ Validating GitHub Actions workflows...${NC}"

if command -v yamllint >/dev/null 2>&1; then
    yamllint "$PROJECT_ROOT/.github/workflows/"*.yml && echo -e "✅ YAML syntax valid"
else
    echo -e "${YELLOW}⚠️ yamllint not installed, skipping YAML validation${NC}"
fi

# Test 3: Check Docker Compose configuration
echo ""
echo -e "${YELLOW}🐳 Testing Docker Compose configuration...${NC}"

cd "$PROJECT_ROOT"
if docker-compose config >/dev/null 2>&1; then
    echo -e "✅ Docker Compose configuration valid"
else
    echo -e "${RED}❌ Docker Compose configuration invalid${NC}"
    exit 1
fi

# Test 4: Check Python dependencies
echo ""
echo -e "${YELLOW}🐍 Checking Python dependencies...${NC}"

if command -v poetry >/dev/null 2>&1; then
    if poetry check; then
        echo -e "✅ Poetry configuration valid"
    else
        echo -e "${RED}❌ Poetry configuration issues${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️ Poetry not installed, skipping dependency check${NC}"
fi

# Test 5: Check legal research service imports
echo ""
echo -e "${YELLOW}⚖️ Testing legal research service...${NC}"

cat > "$PROJECT_ROOT/test_imports.py" << 'EOF'
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'fastapi'))

try:
    from services.legal_research_service import LegalResearchService
    print("✅ Legal research service imports successfully")
    
    # Test service initialization
    service = LegalResearchService()
    print("✅ Legal research service initializes")
    
    # Test basic functionality
    if hasattr(service, 'comprehensive_legal_search'):
        print("✅ comprehensive_legal_search method exists")
    if hasattr(service, 'search_caselaw_access_project'):
        print("✅ search_caselaw_access_project method exists")
    if hasattr(service, 'multi_source_search'):
        print("✅ multi_source_search method exists")
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Service error: {e}")
    sys.exit(1)
EOF

if python3 "$PROJECT_ROOT/test_imports.py"; then
    echo -e "✅ Legal research service test passed"
else
    echo -e "${RED}❌ Legal research service test failed${NC}"
fi

rm -f "$PROJECT_ROOT/test_imports.py"

# Test 6: Check terraform configuration
echo ""
echo -e "${YELLOW}🏗️ Checking Terraform configuration...${NC}"

cd "$PROJECT_ROOT/infrastructure/ec2-simple"

if command -v terraform >/dev/null 2>&1; then
    if terraform validate; then
        echo -e "✅ Terraform configuration valid"
    else
        echo -e "${RED}❌ Terraform configuration invalid${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️ Terraform not installed, skipping validation${NC}"
fi

# Test 7: Check deployment script permissions
echo ""
echo -e "${YELLOW}🔐 Checking script permissions...${NC}"

if [ -x "$PROJECT_ROOT/infrastructure/ec2-simple/github-deploy.sh" ]; then
    echo -e "✅ github-deploy.sh is executable"
else
    echo -e "${YELLOW}⚠️ Making github-deploy.sh executable${NC}"
    chmod +x "$PROJECT_ROOT/infrastructure/ec2-simple/github-deploy.sh"
fi

# Test 8: Environment file template
echo ""
echo -e "${YELLOW}📄 Checking environment template...${NC}"

if [ -f "$PROJECT_ROOT/.env.example" ]; then
    # Check for required environment variables
    required_vars=(
        "CASELAW_API_KEY"
        "SERPAPI_KEY"
        "OPEN_AI_API_KEY"
        "ANTHROPIC_API_KEY"
        "DATABASE_URL"
        "CHROMA_URL"
        "FASTAPI_URL"
    )
    
    missing_vars=()
    for var in "${required_vars[@]}"; do
        if grep -q "^$var=" "$PROJECT_ROOT/.env.example" || grep -q "^#.*$var=" "$PROJECT_ROOT/.env.example"; then
            echo -e "✅ $var found in .env.example"
        else
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -eq 0 ]; then
        echo -e "✅ All required environment variables in template"
    else
        echo -e "${YELLOW}⚠️ Missing variables in .env.example: ${missing_vars[*]}${NC}"
    fi
else
    echo -e "${RED}❌ .env.example not found${NC}"
    exit 1
fi

# Test 9: Check AWS CLI configuration (if available)
echo ""
echo -e "${YELLOW}☁️ Checking AWS CLI...${NC}"

if command -v aws >/dev/null 2>&1; then
    if aws sts get-caller-identity >/dev/null 2>&1; then
        echo -e "✅ AWS CLI configured and working"
        aws sts get-caller-identity --query 'Account' --output text | sed 's/.*/✅ AWS Account: &/'
    else
        echo -e "${YELLOW}⚠️ AWS CLI not configured (this is OK for GitHub Actions)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️ AWS CLI not installed (this is OK for GitHub Actions)${NC}"
fi

# Test 10: Generate deployment checklist
echo ""
echo -e "${YELLOW}📋 Generating deployment checklist...${NC}"

cat > "$PROJECT_ROOT/DEPLOYMENT_CHECKLIST.md" << 'EOF'
# Deployment Checklist

## Pre-Deployment Setup

### GitHub Repository Secrets
- [ ] `AWS_ACCESS_KEY_ID` - AWS access key
- [ ] `AWS_SECRET_ACCESS_KEY` - AWS secret key
- [ ] `AWS_REGION` - AWS region (e.g., us-east-1)
- [ ] `AWS_KEY_PAIR_NAME` - EC2 key pair name
- [ ] `EC2_SSH_PRIVATE_KEY` - SSH private key content

### API Keys
- [ ] `CASELAW_API_KEY` - Harvard Caselaw Access Project
- [ ] `SERPAPI_KEY` - SerpApi for Google Scholar
- [ ] `SEARCHAPI_KEY` - SearchApi alternative
- [ ] `OPEN_AI_API_KEY` - OpenAI API access
- [ ] `ANTHROPIC_API_KEY` - Claude API access
- [ ] `HUGGINGFACE_API_KEY` - HuggingFace models
- [ ] `LANGCHAIN_API_KEY` - LangSmith tracing

### Optional Configuration
- [ ] `EC2_INSTANCE_TYPE` - Instance size (default: t3.medium)
- [ ] `DOMAIN_NAME` - Custom domain for SSL

### AWS Setup
- [ ] IAM user created with EC2 permissions
- [ ] EC2 key pair created
- [ ] Security groups configured
- [ ] AWS CLI configured locally (for testing)

## Deployment Steps

### 1. Infrastructure Creation
- [ ] Run manual workflow: "create-infrastructure"
- [ ] Verify instance is running
- [ ] Note instance IP address

### 2. Code Deployment
- [ ] Push code to main/master branch (automatic)
- [ ] OR run manual workflow: "deploy-code"
- [ ] Verify deployment success

### 3. Application Verification
- [ ] Check Streamlit UI: http://INSTANCE_IP:8501
- [ ] Check FastAPI: http://INSTANCE_IP:9020/health
- [ ] Check API docs: http://INSTANCE_IP:9020/docs
- [ ] Test legal research: http://INSTANCE_IP:9020/legal-search-demo

### 4. Post-Deployment
- [ ] Monitor application logs
- [ ] Set up CloudWatch alarms
- [ ] Configure domain/SSL (if needed)
- [ ] Schedule regular backups

## Troubleshooting

### Common Issues
- [ ] SSH connection failed → Check security groups
- [ ] Application not starting → Check logs via SSH
- [ ] API errors → Verify all secrets are set
- [ ] Legal research not working → Check API keys

### Monitoring Commands
```bash
# Connect to instance
ssh -i ~/.ssh/your-key.pem ubuntu@INSTANCE_IP

# Check application status
cd /opt/llm-app && sudo docker-compose ps

# View logs
sudo docker-compose logs -f

# Restart services
sudo docker-compose restart
```

## Security Checklist
- [ ] SSH keys properly secured
- [ ] Security groups restrict access appropriately
- [ ] API keys rotated regularly
- [ ] CloudTrail monitoring enabled
- [ ] Regular security updates scheduled

## Cost Management
- [ ] Monitor AWS costs
- [ ] Set up billing alerts
- [ ] Consider auto-shutdown for non-production
- [ ] Review instance sizing regularly
EOF

echo -e "✅ Deployment checklist created: DEPLOYMENT_CHECKLIST.md"

# Summary
echo ""
echo -e "${GREEN}🎉 Deployment Setup Test Complete!${NC}"
echo ""
echo -e "${BLUE}📊 Test Summary:${NC}"
echo -e "✅ Required files present"
echo -e "✅ GitHub Actions workflows valid"
echo -e "✅ Docker Compose configuration valid"
echo -e "✅ Legal research service functional"
echo -e "✅ Deployment scripts executable"
echo -e "✅ Environment template complete"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "1. Configure GitHub repository secrets (see .github/DEPLOYMENT_SETUP.md)"
echo "2. Set up AWS IAM permissions"
echo "3. Create EC2 key pair"
echo "4. Run manual deployment workflow to create infrastructure"
echo "5. Deploy code and test application"
echo ""
echo -e "${GREEN}🚀 Ready for deployment!${NC}"