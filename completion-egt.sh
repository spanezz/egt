_egt() {
    COMPREPLY=()
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"

    case "$prev" in
        egt)
            local commands=$(egt completion commands)
            COMPREPLY=($(compgen -W "$commands" -- "$cur"))
            return 0
        ;;
        -t|--tag)
            local tags=$(egt completion tags)
            COMPREPLY=($(compgen -W "$tags" -- "$cur"))
        ;;
    esac

    local base="${COMP_WORDS[1]}"
    case "$base" in
        edit|grep|term|work|cat)
            local projects=$(egt completion projects)
            COMPREPLY=($(compgen -W "$projects" -- "$cur"))
        ;;
    esac
    return 0
} 
complete -F _egt egt
