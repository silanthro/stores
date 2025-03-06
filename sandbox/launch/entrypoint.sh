#!/bin/bash
set -e

export DISPLAY=:${DISPLAY_NUM}

DisplayHelp()
{
   # Display Help
   echo "Call tool by tool name (-t) and kwargs (-a)"
   echo
   echo "Usage: $0 -t <string> -a <string>" 1>&2
   exit 0
}

# Main program
while getopts ":ht:a:" option; do
    case $option in
        h)
            DisplayHelp
            exit;;
        t)
            tool=${OPTARG}
            ;;
        a)
            kwargs=${OPTARG}
            # Sanitize kwargs
            printf -v clean_kwargs "%q" "$kwargs"
            ;;
        \?)
            echo "Error: Invalid option"
            DisplayHelp
            exit;;
   esac
done

# Initialize xvfb and mutter
./launch/xvfb_startup.sh
./launch/mutter_startup.sh

# Run call_tool script
echo -t ${tool} -a ${clean_kwargs}|xargs uv run python -m tools.call_tool
