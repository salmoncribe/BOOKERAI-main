#!/bin/bash
cd "$(dirname "$0")"
if [ -f .env ]; then
    export $(cat .env | xargs)
fi
echo "URL: '$SUPABASE_URL'"
echo "KEY: '$SUPABASE_KEY'"
python3 -c "import os; print('Python URL:', os.environ.get('SUPABASE_URL')); print('Python KEY:', os.environ.get('SUPABASE_KEY'))"
