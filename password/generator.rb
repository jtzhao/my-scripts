#!/usr/bin/env ruby

# Requirements:
# Must be at least 8 characters long.
# Must include at least 1 number.
# Must not repeat any character sequentially more than 3 times.
# Must have at least 1 lowercase letter.
# Must have at least 1 uppercase letter.
# Must not include part of your name or username.
# Must not include a common word or commonly used sequence of characters.
# New password may not have been used previously.


# ascii: 48 - 57
def rand_digit
    ascii = Random.rand(10) + 48
    return ascii.chr
end

# ascii: 65 - 90
def rand_upper_letter
    ascii = Random.rand(26) + 65
    return ascii.chr
end

# ascii: 97 - 122
def rand_lower_letter
    ascii = Random.rand(26) + 97
    return ascii.chr
end

# ascii: 33 - 126
def rand_char
    ascii = Random.rand(94) + 33
    return ascii.chr
end

def generate(length=8)
    # check password length
    if length < 8
        raise ValueError.new("Password must be at least 8 characters long.")
    end
    password = Array.new(length, nil)
    # init random seed
    Random.srand
    # 1 number
    pos = Random.rand(length)
    password[pos] = rand_digit
    # 1 uppercase letter
    pos = Random.rand(length)
    while password[pos] != nil
        pos = Random.rand(length)
    end
    password[pos] = rand_upper_letter
    # 1 lowercase letter
    pos = Random.rand(length)
    while password[pos] != nil
        pos = Random.rand(length)
    end
    password[pos] = rand_lower_letter
    # remaining characters
    for pos in 0..(length-1)
        if password[pos] == nil
            password[pos] = rand_char
        end
    end
    return password.join('')
end


if __FILE__ == $0
    puts generate
end
