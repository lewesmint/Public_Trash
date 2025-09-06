#!/usr/bin/env bash

# Function to prompt for name and email until non-empty
prompt_identity() {
  while [ -z "$NAME" ]; do
    read -r -p "Enter your Git user.name: " NAME
  done
  while [ -z "$EMAIL" ]; do
    read -r -p "Enter your Git user.email: " EMAIL
  done
}

# Read current config (empty if unset)
NAME=$(git config --global --get user.name)
EMAIL=$(git config --global --get user.email)

if [ -n "$NAME" ] && [ -n "$EMAIL" ]; then
  echo "Current Git global identity:"
  echo "  Name : $NAME"
  echo "  Email: $EMAIL"
  read -r -p "Do you want to keep these settings? (Y/n): " CONFIRM
  if [[ ! ( -z "$CONFIRM" || "$CONFIRM" =~ ^[Yy] ) ]]; then
    prompt_identity
  else
    echo "Keeping existing settings."
  fi
else
  echo "Git global user settings are not fully set."
  read -r -p "Do you want to set them now? (Y/n): " CONFIRM
  if [[ -z "$CONFIRM" || "$CONFIRM" =~ ^[Yy] ]]; then
    prompt_identity
  else
    echo "Leaving Git global user unset."
    NAME=""
    EMAIL=""
  fi
fi

# Apply only if both values are present
if [ -n "$NAME" ] && [ -n "$EMAIL" ]; then
  git config --global user.name "$NAME"
  git config --global user.email "$EMAIL"
  echo "Final Git global identity:"
  echo "  Name : $(git config --global --get user.name)"
  echo "  Email: $(git config --global --get user.email)"
else
  echo "Git global identity not configured."
fi
