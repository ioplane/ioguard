# GnuTLS Performance Baseline

**Date:** October 29, 2025  
**Sprint:** Sprint 1, Task 6  
**Backend:** GnuTLS 3.8.9

## System Specifications

**Hardware:**
- CPU: AMD EPYC Processor
- RAM: 15 GB (8.8 GB available)
- Architecture: x86_64

**Software:**
- OS: Oracle Linux 10
- Kernel: 6.12.0-104.43.4.2.el10uek.x86_64
- GnuTLS: 3.8.9
- GCC: 14.2.1 (C23 standard)

## Performance Results

### Handshake Performance
- **Handshake time:** 2.109 ms
- **Protocol:** TLS 1.3
- **Cipher suite:** AES-256-GCM

### Throughput (100 iterations per size)

| Payload Size | Throughput | Latency |
|--------------|------------|---------|
| 1 B          | 0.00 MB/s  | 0.448 ms |
| 64 B         | 3.03 MB/s  | 0.040 ms |
| 256 B        | 17.03 MB/s | 0.029 ms |
| 1024 B       | 47.54 MB/s | 0.041 ms |
| 4096 B       | 167.85 MB/s| 0.047 ms |
| 16384 B      | 403.65 MB/s| 0.077 ms |

### Resource Usage

**During benchmark execution:**
- Memory (RSS): 5.0 MB
- Memory (VSZ): 8.9 MB
- CPU usage: 0.9%

## Analysis

### Strengths
1. **Fast handshake:** 2.1 ms is excellent for TLS 1.3
2. **Good throughput scaling:** Performance improves with larger payloads
3. **Low memory footprint:** Only 5 MB RSS
4. **Minimal CPU usage:** <1% during benchmark

### Observations
1. Small payloads (1-64 bytes) have higher relative latency due to TLS overhead
2. Throughput peaks at ~400 MB/s for 16KB payloads
3. Linear scaling from 256B to 16KB suggests efficient buffering

## GO/NO-GO Criteria for wolfSSL

For wolfSSL to receive a **GO** decision, it must achieve:

**Option A: Performance parity**
- Handshake time: 1.899-2.320 ms (±10% of 2.109 ms)
- Throughput: 363.29-443.99 MB/s (±10% of 403.65 MB/s for 16KB)

**OR**

**Option B: CPU efficiency**
- At least 10% reduction in CPU usage (≤0.81%)

### Next Steps
1. Run wolfSSL benchmark with identical parameters (Task 7)
2. Compare results using `uv run --script ./tests/poc/compare.py`
3. Make GO/NO-GO decision based on criteria above
4. Document decision rationale

---

**Files:**
- Results: `docs/benchmarks/gnutls_baseline.json/results_gnutls_20251029_104527.json`
- Resources: `docs/benchmarks/gnutls_baseline.json/resources_gnutls_20251029_104527.txt`
- Server log: `docs/benchmarks/gnutls_baseline.json/server_gnutls_20251029_104527.log`
