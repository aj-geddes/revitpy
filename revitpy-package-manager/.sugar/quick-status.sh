#!/bin/bash
# Quick task status display

echo "🔍 SUGAR TASK STATUS"
echo "===================="
echo ""

cd "$(dirname "$0")"

if ! command -v jq &> /dev/null; then
    echo "⚠️  jq not installed. Install with: apt install jq"
    exit 1
fi

total=$(jq '.metadata.total_tasks' tasks.json)
completed=$(jq '[.tasks[] | select(.status == "completed")] | length' tasks.json)
in_progress=$(jq '[.tasks[] | select(.status == "in_progress")] | length' tasks.json)
pending=$(jq '[.tasks[] | select(.status == "pending")] | length' tasks.json)

pct=$((completed * 100 / total))

echo "📊 Overall Progress"
echo "  Total Tasks:    $total"
echo "  ✅ Completed:   $completed ($pct%)"
echo "  🔄 In Progress: $in_progress"
echo "  ⏭️  Pending:     $pending"
echo ""

echo "🚨 Critical Tasks (Priority 5)"
jq -r '.tasks[] | select(.priority == 5) | "  [\(.status | if . == "completed" then "✅" elif . == "in_progress" then "🔄" else "⏭️ " end)] \(.id): \(.title)"' tasks.json
echo ""

echo "⚡ Quick Wins (< 30 min)"
jq -r '.tasks[] | select(.estimated_effort_minutes != null and .estimated_effort_minutes < 30 and .status != "completed") | "  [\(.status | if . == "in_progress" then "🔄" else "⏭️ " end)] \(.id): \(.title) (\(.estimated_effort_minutes)m)"' tasks.json
echo ""

echo "For full details: cat .sugar/TASK_SUMMARY.md"
