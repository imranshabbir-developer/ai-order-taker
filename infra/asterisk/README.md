# Asterisk 20 telephony scaffold (Sprint 5)

Local development placeholder for SIP + ARI bridging to the voice agent WebSocket.

## Status

Not wired to production SIP yet. Use the browser voice client (`run_voice_server.py`) until a SIP trunk is provisioned.

## Planned layout

```
infra/asterisk/
  docker-compose.asterisk.yml   # Asterisk + optional rtpengine
  configs/
    pjsip.conf                  # SIP trunk + extensions
    extensions.conf             # Dialplan → Stasis/ARI
    ari.conf                    # ARI user for voice-agent bridge
```

## Next steps (Sprint 5)

1. Provision Hetzner VPS or use client SIP trunk (Telnyx / VoIP.ms).
2. Configure PJSIP endpoint for inbound DID.
3. ARI External Media → `ws://voice-agent:8090/ws/voice/{call_id}`.
4. Pass caller ID to order-api for post-order lookup (Test 14).
5. SIP transfer to `escalation_staff_phone` from restaurant operations config.

## References

- [Asterisk ARI](https://docs.asterisk.org/Configuration/Interfaces/Asterisk-REST-Interface-ARI/)
- IMPLEMENTATION_PLAN.md Sprint 5 tasks 5.1–5.7
