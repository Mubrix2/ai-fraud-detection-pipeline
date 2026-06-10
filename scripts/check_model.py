import sys
from pathlib import Path

required = [
    'app/models/fraud_model.pkl',
    'app/models/anomaly_model.pkl',
    'app/models/scaler.pkl',
]
missing = [m for m in required if not Path(m).exists()]
if missing:
    print('ERROR: Missing model files:')
    for m in missing:
        print(f'  {m}')
    print()
    print('Run these scripts before building Docker:')
    print('  python scripts/prepare_data.py')
    print('  python scripts/train_fraud_model.py')
    print('  python scripts/train_anomaly_model.py')
    sys.exit(1)
print(f'All {len(required)} model files verified.')
