#!/usr/bin/env bash

set -euo pipefail

readonly CI_BUILD_TYPES_KEYWORD="CI build types:"
GIT_HEAD_COMMIT_MESSAGE=$( git log --format=%B -n 1 --no-merges )
readonly GIT_HEAD_COMMIT_MESSAGE

echo
echo "--------------------------------------------------------------------------------------------"
echo "Git HEAD commit message:"
echo
echo "$GIT_HEAD_COMMIT_MESSAGE"
echo
echo "--------------------------------------------------------------------------------------------"
echo

build_type=$YB_THIRDPARTY_ARCHIVE_NAME_SUFFIX
echo "Build type: $build_type"

# A quick way to filter build types in the commit message.
should_build=true
if [[ $GIT_HEAD_COMMIT_MESSAGE == *"$CI_BUILD_TYPES_KEYWORD"* ]]; then

  # The commit message includes a line such as the following:
  #
  # CI build types: centos7-x86_64-clang15, centos7-x86_64-clang15-full-lto, centos7-x86_64-clang16,
  # centos7-x86_64-clang16-full-lto

  # This syntax in the commit message allows us to only build a subset of build types for a
  # particular commit / pull request. The build jobs are still started for all build types, but they
  # finish very quickly if the build type is filtered out.

  # Extract build types from the commit message. We always expect to get a match from this grep
  # command.
  set +e
  build_types_str=$(
    grep -Eo "$CI_BUILD_TYPES_KEYWORD.*" <<< "$GIT_HEAD_COMMIT_MESSAGE"
  )
  build_types_str=${build_types_str//${CI_BUILD_TYPES_KEYWORD}/ }
  if [[ -z "$build_types_str" ]]; then
    echo >&2 "Internal error: could not parse the build type patterns from the commit message."
    exit 1
  fi
  set -e

  # Convert the build types to an array, trimming spaces manually
  IFS=',' read -r -a build_type_patterns_tmp_array <<< "$build_types_str"
  build_type_patterns_array=()
  for build_type_pattern in "${build_type_patterns_tmp_array[@]}"; do
    # Remove leading/trailing whitespace.
    build_type_pattern=${build_type_pattern#"${build_type_pattern%%[![:space:]]*}"}
    build_type_pattern=${build_type_pattern%"${build_type_pattern##*[![:space:]]}"}

    build_type_patterns_array+=( "$build_type_pattern" )
    if [[ $build_type_pattern == *linux* ]]; then
      echo >&2 "Expanding pattern '$build_type_pattern' to match all Linux distributions."
      build_type_patterns_array+=(
        "${build_type_pattern//linux/almalinux}"
        "${build_type_pattern//linux/amazonlinux}"
        "${build_type_pattern//linux/centos}"
        "${build_type_pattern//linux/ubuntu}"
      )
    fi
  done

  echo >&2 "Final list of build type patterns: ${build_type_patterns_array[*]}"

  should_build=false

  pattern_parsing_error=false
  for build_type_pattern in "${build_type_patterns_array[@]}"; do
    build_type_pattern="*${build_type_pattern}*"
    if [[ $build_type_pattern =~ ^[a-zA-Z0-9*-_]+$ ]]; then
      # The absence of quotes around $build_type_pattern is intentional. We allow asterisk wildcard
      # matching.
      # shellcheck disable=SC2053
      if [[ "$build_type" == $build_type_pattern ]]; then
        echo >&2 "Build type '$build_type' matched pattern" \
                 "'$build_type_pattern', proceeding with the build."
        should_build=true
      else
        echo >&2 "Build type '$build_type' did not match pattern '$build_type_pattern'"
      fi
    else
      echo >&2 "Warning: skipping invalid build type pattern '$build_type_pattern'. It must" \
               "consist of letters, numbers, dashes, underscores, and asterisks."
      pattern_parsing_error=true
    fi
  done
  if [[ $pattern_parsing_error == "true" ]]; then
    exit 1
  fi
fi

if [[ $should_build == "true" ]]; then
  if [[ $OSTYPE == darwin* ]]; then
    ./.github/workflows/macos_build.sh
  else
    ./.github/workflows/linux_build.sh
  fi
else
  echo "Build type $build_type filtered out by the" \
       "'$CI_BUILD_TYPES_KEYWORD' commit message filter."
fi
