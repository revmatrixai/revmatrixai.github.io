# RevMatrix — Demo Trials Backend

> Enterprise-grade demo system for [revmatrixai.github.io](https://revmatrixai.github.io)  
> Zero cost · Privacy-first · Multi-language · Pull-request ready

---

## 📁 Repository Structure

```
revmatrix-demos/
├── backend/                  # FastAPI backend (deploy free on Render)
│   ├── main.py               # API server with rate limiting + security
│   ├── requirements.txt
│   └── Dockerfile
├── demos/
│   ├── web/                  # HTML/CSS/JS live editor demo
│   ├── cybersecurity/        # Python vulnerability scanner demo
│   │   └── scanner.py
│   ├── ai/                   # Neural network training demo
│   │   ├── neural_net.py
│   │   └── requirements.txt
│   ├── agents/               # Multi-agent AI system demo
│   │   ├── crew_demo.py
│   │   └── requirements.txt
│   ├── quantum/              # Quantum computing demos
│   │   ├── bell_state.py     # Qiskit local simulation
│   │   ├── quafu_demo.py     # Quafu (夸父) real quantum cloud
│   │   └── requirements.txt
│   └── devops/               # Cloud & DevOps demo
│       ├── deploy.sh
│       ├── Dockerfile
│       └── k8s-deployment.yaml
├── .github/
│   └── workflows/
│       └── security-scan.yml # Auto security scanning on PR
├── .gitignore
└── SECURITY.md
```

---

## 🚀 Zero-Cost Deployment Options

| Service | What it hosts | Free tier |
|---------|--------------|-----------|
| **GitHub Pages** | Frontend website | Unlimited |
| **Render.com** | FastAPI backend | 750 hrs/month |
| **Railway.app** | FastAPI backend | $5 credit/month |
| **Deta Space** | Python microservices | Free forever |
| **Quafu (夸父)** | Real quantum computer | Free account |
| **IBM Quantum** | 127-qubit quantum | Free account |

---

## ⚡ Quick Start (Local)

```bash
# Clone
git clone https://github.com/revmatrixai/revmatrix-demos
cd revmatrix-demos

# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Test
curl http://localhost:8000/health
```

---

## 🔒 Security Features

- Rate limiting per IP (10 req/min)
- Input sanitization on all endpoints  
- CORS restricted to revmatrixai.github.io
- No API keys stored in repo (env vars only)
- Automated Trivy security scanning on every PR
- No user data stored — stateless architecture

---

## 🤝 Contributing via Pull Request

1. Fork this repo from your secondary GitHub account
2. Create branch: `feature/your-improvement`
3. Make changes (follow security guidelines in SECURITY.md)
4. Open PR → auto security scan runs
5. Merge after review

---

## ⚛️ Free Quantum Resources

| Platform | Qubits | Access |
|----------|--------|--------|
| [Quafu 夸父](https://quafu.baqis.ac.cn) 🇨🇳 | 10–136 | Free account |
| [IBM Quantum](https://quantum.ibm.com) | 127 | Free account |
| [Google Cirq](https://quantumai.google) | Simulator | Free |
| [Amazon Braket Free](https://aws.amazon.com/braket/free-tier/) | Simulator | Free tier |

---

*Built by RevMatrix — AI-Powered Virtual Solutions*
